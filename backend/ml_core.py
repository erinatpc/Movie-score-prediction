"""Núcleo de ML compartido por el notebook y el servicio.

Una única fuente de verdad para: preparación de datos, transformadores propios y construcción de pipelines.
Debe poder importarse como módulo de nivel superior (`import ml_core`): `joblib` guarda las clases del
modelo con ese nombre de módulo.
"""
import re
from bisect import bisect_left

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (ExtraTreesRegressor, HistGradientBoostingRegressor,
                              RandomForestRegressor, VotingRegressor)
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer, KNNImputer, SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
ENTITY_COLS = ["director", "writer", "star", "company"]
CAT_COLS = ["genre", "rating", "country", "release_month"]
NUM_COLS = ["year", "runtime", "log_budget", "budget_missing"]
INPUT_COLS = ENTITY_COLS + CAT_COLS + NUM_COLS
FORBIDDEN_COLS = ["votes", "gross", "released", "name"]

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
PLACEHOLDER_NAMES = {"Directors"}
ENSEMBLE_MEMBERS = ["random_forest", "extra_trees", "hist_gb"]


# --------------------------------------------------------------------------- datos
def _month_from_released(s):
    if not isinstance(s, str):
        return np.nan
    m = re.match(r"^([A-Za-z]+)\s+\d{1,2},", s)
    return m.group(1) if m and m.group(1) in MONTHS else np.nan


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Registros crudos -> columnas de entrada del modelo. Ignora votes, gross, name y fecha exacta."""
    out = pd.DataFrame(index=df.index)
    for c in ["director", "writer", "star", "company", "genre", "rating", "country"]:
        s = df[c] if c in df else pd.Series(np.nan, index=df.index)
        out[c] = s.where(~s.isin(PLACEHOLDER_NAMES))
    if "release_month" in df:
        out["release_month"] = df["release_month"]
    elif "released" in df:
        out["release_month"] = df["released"].map(_month_from_released)
    else:
        out["release_month"] = np.nan
    out["year"] = df["year"].astype(float)
    out["runtime"] = df["runtime"].astype(float) if "runtime" in df else np.nan
    budget = df["budget"].astype(float) if "budget" in df else pd.Series(np.nan, index=df.index)
    budget = budget.where(budget > 0)
    out["log_budget"] = np.log1p(budget)
    out["budget_missing"] = budget.isna().astype(float)
    return out[INPUT_COLS]


# --------------------------------------------------------------------------- transformadores
class HistoryEncoder(BaseEstimator, TransformerMixin):
    """Historial previo sin fuga: usa solo películas de años ANTERIORES de cada entidad."""

    def __init__(self, cols=tuple(ENTITY_COLS), smoothing=5.0):
        self.cols = cols
        self.smoothing = smoothing

    def fit(self, X, y):
        y = np.asarray(y, dtype=float)
        self.global_mean_ = float(y.mean())
        self.index_ = {}
        for c in self.cols:
            tmp = pd.DataFrame({"e": X[c].values, "y": y, "yr": X["year"].values}).dropna(subset=["e"])
            idx = {}
            for e, g in tmp.sort_values("yr").groupby("e"):
                idx[e] = (g["yr"].to_numpy(), np.concatenate([[0.0], np.cumsum(g["y"].to_numpy())]))
            self.index_[c] = idx
        return self

    def transform(self, X):
        n_rows, years, out = len(X), X["year"].to_numpy(), {}
        for c in self.cols:
            n, m = np.zeros(n_rows), np.full(n_rows, self.global_mean_)
            for i, e in enumerate(X[c].to_numpy()):
                rec = self.index_[c].get(e) if isinstance(e, str) else None
                if rec is None:
                    continue
                k = bisect_left(rec[0], years[i])        # nº de películas con año < año actual
                n[i] = k
                m[i] = (rec[1][k] + self.smoothing * self.global_mean_) / (k + self.smoothing)
            out[f"{c}_prev_n"] = np.log1p(n)
            out[f"{c}_prev_mean"] = m
        return pd.DataFrame(out, index=X.index)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"{c}_{s}" for c in self.cols for s in ("prev_n", "prev_mean")])


class GenreYearBudgetImputer(BaseEstimator, TransformerMixin):
    """Imputa log_budget con la mediana por (género, bloque de 5 años) -> género -> global."""

    def __init__(self, bucket=5):
        self.bucket = bucket

    def _key(self, X):
        return (X["year"] // self.bucket * self.bucket).astype(int)

    def fit(self, X, y=None):
        known = X[X["log_budget"].notna()]
        self.global_ = float(known["log_budget"].median())
        self.by_genre_ = known.groupby("genre")["log_budget"].median().to_dict()
        self.by_gb_ = known.assign(_b=self._key(known)).groupby(["genre", "_b"])["log_budget"].median().to_dict()
        return self

    def transform(self, X):
        X = X.copy()
        miss = X["log_budget"].isna()
        if miss.any():
            b = self._key(X)
            X.loc[miss, "log_budget"] = [self.by_gb_.get((g, k), self.by_genre_.get(g, self.global_))
                                        for g, k in zip(X.loc[miss, "genre"], b[miss])]
        return X


# --------------------------------------------------------------------------- pipelines
def build_preprocessor(imputer="genre_year", scale=False):
    """imputer: median | genre_year | knn | iterative | native (deja NaN; solo para HistGradientBoosting)."""
    num_cols = ["year", "runtime", "log_budget", "budget_missing"]
    if imputer in ("median", "genre_year"):
        steps = [("imp", SimpleImputer(strategy="median"))]
    elif imputer == "knn":
        steps = [("sc0", StandardScaler()), ("imp", KNNImputer(n_neighbors=10))]
    elif imputer == "iterative":
        steps = [("imp", IterativeImputer(max_iter=10, random_state=SEED))]
    elif imputer == "native":
        steps = []
    else:
        raise ValueError(imputer)
    if scale and imputer != "native":
        steps.append(("sc", StandardScaler()))
    num_branch = Pipeline(steps) if steps else "passthrough"
    cat_branch = Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="desconocido")),
                           ("ohe", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=30,
                                                 sparse_output=False))])
    hist_branch = Pipeline([("h", HistoryEncoder())] + ([("sc", StandardScaler())] if scale else []))
    ct = ColumnTransformer([("hist", hist_branch, ENTITY_COLS + ["year"]),
                            ("num", num_branch, num_cols),
                            ("cat", cat_branch, CAT_COLS)], verbose_feature_names_out=False)
    pre = [("budget_imp", GenreYearBudgetImputer())] if imputer == "genre_year" else []
    return Pipeline(pre + [("prep", ct)])


def make_model(name):
    models = {
        "media (baseline)": DummyRegressor(strategy="mean"),
        "ridge": Ridge(alpha=10.0),
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.5,
                                               n_jobs=-1, random_state=SEED),
        "extra_trees": ExtraTreesRegressor(n_estimators=300, min_samples_leaf=5, max_features=0.5,
                                           n_jobs=-1, random_state=SEED),
        "hist_gb": HistGradientBoostingRegressor(learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                                 min_samples_leaf=20, l2_regularization=1.0, random_state=SEED),
    }
    return models[name]


def build_pipeline(name="hist_gb", imputer="genre_year", model=None):
    prep = build_preprocessor("median") if name == "media (baseline)" else \
        build_preprocessor(imputer, scale=(name == "ridge"))
    return Pipeline([("prep", prep), ("model", model if model is not None else make_model(name))])


def make_ensemble(tuned, imputer="genre_year"):
    """Promedio (Voting) de RF + ExtraTrees + HistGB con los hiperparámetros ya ajustados."""
    est = [(n, make_model(n).set_params(**tuned[n])) for n in ENSEMBLE_MEMBERS]
    return Pipeline([("prep", build_preprocessor(imputer)), ("model", VotingRegressor(est))])


def build_final_pipeline(algorithm, hyperparameters, imputer="genre_year"):
    """Reconstruye (sin entrenar) el pipeline de un modelo guardado a partir de sus metadatos."""
    if algorithm.startswith("ensamble"):
        return make_ensemble(hyperparameters, imputer)
    key = algorithm.replace(" (tuneado)", "")
    return build_pipeline(key, imputer=imputer, model=make_model(key).set_params(**hyperparameters[key]))


def regression_metrics(y_true, y_pred):
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "r2": float(r2_score(y_true, y_pred))}


# --------------------------------------------------------------------------- utilidades de inferencia
def _history_encoder(pipeline):
    """Localiza el HistoryEncoder dentro de un pipeline entrenado (None si no existe)."""
    try:
        prep = pipeline.named_steps["prep"]
        ct = prep.named_steps["prep"]
        return ct.named_transformers_["hist"].named_steps["h"]
    except (KeyError, AttributeError):
        return None


def entity_history(pipeline, col, name, year):
    """Nº de películas previas (año < `year`) de una entidad en el entrenamiento del modelo.
    Devuelve None si no se puede determinar."""
    enc = _history_encoder(pipeline)
    if enc is None or not isinstance(name, str):
        return 0 if enc is not None else None
    rec = enc.index_.get(col, {}).get(name)
    return 0 if rec is None else int(bisect_left(rec[0], year))

from datetime import datetime
from pydantic import BaseModel

class DatasetParams(BaseModel):
    branch_id: int
    date_from: datetime
    date_to: datetime
    features: list[str] = ["co2", "temp", "rh", "people"]
    targets: list[str] = ["co2", "temp", "rh"]

class FeatureEngineeringParams(BaseModel):
    lags: list[int] = [1, 2, 3, 5, 10, 20]
    rolls: list[int] = [5, 10, 20]
    use_time_features: bool = True
    use_diff_features: bool = True
    use_occupancy: bool = True
    use_interaction: bool = True

class ForecastParams(BaseModel):
    horizon: int = 15
    step_ahead: int = 10

class ModelHyperparams(BaseModel):
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.03
    subsample: float = 0.8
    colsample_bytree: float = 0.8

class JobCreateRequest(BaseModel):
    dataset: DatasetParams
    feature_engineering: FeatureEngineeringParams
    forecast: ForecastParams
    model_hyperparams: ModelHyperparams

class JobUpdateRequest(BaseModel):
    secret: str
    status: str
    result: dict | None = None
    message: str | None = None
    model_id: str | None = None
    model_name: str | None = None

class JobResponse(BaseModel):
    job_id: str
    branch_id: int
    user_id: int | None = None
    status: str
    message: str | None = None
    secret: str | None = None
    created_at: datetime
    updated_at: datetime
    dataset_params: dict
    feature_engineering_params: dict
    forecast_params: dict
    model_hyperparams: dict
    result: dict | None = None
    model_id: str | None = None
    model_name: str | None = None

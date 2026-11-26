"""全局配置。所有可调参数集中在这里，方便讲解与二次开发。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

CUSTOMERS_CSV = PROCESSED_DIR / "customers.csv"
META_JSON = PROCESSED_DIR / "dataset_meta.json"
SAMPLE_CSV = RAW_DIR / "ifood_df_sample.csv"

# 分群维度：KMeans 使用的数值特征
CLUSTER_FEATURES = [
    "income",
    "total_spend",
    "purchase_freq",
    "recency",
    "num_deals",
    "web_visits_month",
    "age",
]

# 品类列表，顺序即展示顺序
CATEGORY_FIELDS = {
    "mnt_wines": "葡萄酒",
    "mnt_fruits": "水果",
    "mnt_meat": "肉类",
    "mnt_fish": "鱼类",
    "mnt_sweet": "甜食",
    "mnt_gold": "金饰礼品",
}

CHANNEL_FIELDS = {
    "num_web": "线上商城",
    "num_catalog": "邮购目录",
    "num_store": "线下门店",
}


@dataclass
class Settings:
    """运行期配置，全部支持环境变量覆盖。"""

    app_name: str = "Customer Insight Agent"
    version: str = "1.0.0"
    cluster_k: int = int(os.getenv("CLUSTER_K", "4"))
    random_state: int = int(os.getenv("RANDOM_STATE", "42"))
    # 在线大模型（OpenAI 兼容协议）。留空则自动降级为离线规则引擎。
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "30"))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(",")
    )

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key)


settings = Settings()

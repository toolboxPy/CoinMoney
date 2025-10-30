# master/__init__.py

# 기존 import
from master.global_risk import global_risk
from master.controller import master_controller  # v1.0 (백업)

# 🆕 새로운 import 추가
from master.controller_v3 import smart_controller

__all__ = [
    'global_risk',
    'master_controller',  # v1.0 (백업용)
    'smart_controller'    # 🆕 v3.0 (메인)
]
# ai/__init__.py

# 기존 import (유지)
from ai.multi_ai_analyzer import multi_ai

# 🆕 새로운 import 추가
from ai.ai_call_trigger import ai_trigger
from ai.multi_ai_debate_v2 import debate_system

__all__ = [
    'multi_ai',          # v1.0 (백업용)
    'ai_trigger',        # 🆕 트리거 시스템
    'debate_system'      # 🆕 AI 토론 v2.0
]
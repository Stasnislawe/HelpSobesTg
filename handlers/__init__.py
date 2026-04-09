from .start import router as start_router
from .settings import router as settings_router
from .stats import router as stats_router
from .intensive import router as intensive_router
from .quiz import router as quiz_router
from .cancel import router as cancel_router
from .learning import router as learning_router


routers = [learning_router, start_router, settings_router, stats_router, intensive_router, quiz_router, cancel_router]
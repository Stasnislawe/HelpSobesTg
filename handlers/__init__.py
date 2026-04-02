from .start import router as start_router
from .settings import router as settings_router
from .stats import router as stats_router
from .quiz import router as quiz_router
from .cancel import router as cancel_router


routers = [start_router, settings_router, stats_router, quiz_router, cancel_router]
from app.db import get_session

# re-exported so routers can `Depends(get_db)` with a friendlier name
get_db = get_session

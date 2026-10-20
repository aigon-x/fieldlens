"""HTTP entry point for the public demo: FastAPI served through API Gateway/Lambda URLs."""
from mangum import Mangum

from web.server import app

handler = Mangum(app, lifespan="off")

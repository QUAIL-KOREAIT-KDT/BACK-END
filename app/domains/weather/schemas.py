# BACK-END/app/domains/weather/schemas.py
from pydantic import BaseModel

class ImageData(BaseModel):
    imgdata: str
    window_direction: str
    mold_location: str
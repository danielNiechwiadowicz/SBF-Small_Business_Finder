import tomllib

def load_region(path):
    with open(path, "rb") as f:
        region = tomllib.load(f)
    for key in ("name", "centers", "github_location"):
        if key not in region:
            raise ValueError(f"{path} is missing '{key}'")
        for label, (lat,lng) in region["centers"].items():
            if not (-90 <=lat <= 90 and -180 <= lng <= 180):
                raise ValueError(f"Bad cpprdomates for {label}")
        return region
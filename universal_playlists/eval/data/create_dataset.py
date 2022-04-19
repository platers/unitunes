import json
from pathlib import Path
from universal_playlists.services.services import *
import os
import pandas as pd
from tqdm import tqdm


def main():
    os.chdir(Path(__file__).parent)

    sp = Spotify("spotify", Path("service_configs/spotify_config.json"))

    sp_uris = []
    ytm_uris = []
    mb_uris = []

    filepath = "ytm-spotify-raw"
    with tqdm(total=os.path.getsize(filepath)) as pbar:
        with open(filepath, "r") as f:
            # loop through lines
            for line in tqdm(f):
                pbar.update(len(line))
                raw = json.loads(line)
                relations = raw["relations"]

                spotify_album_id = None
                ytm_track_id = None
                for relation in relations:
                    if "url" in relation:
                        url = relation["url"]
                        if "spotify" in url["resource"]:
                            spotify_album_id = url["resource"]
                        if "music.youtube" in url["resource"]:
                            ytm_track_id = url["resource"]

                if spotify_album_id and ytm_track_id:
                    if spotify_album_id.startswith(
                        "https://open.spotify"
                    ) and ytm_track_id.startswith("https://music.youtube"):
                        tracks = sp.get_tracks_in_album(SpotifyURI(spotify_album_id))
                        sp_track = tracks[0]

                        sp_uris.append(sp_track.uris[0].uri.split("/")[-1])
                        ytm_track_id = ytm_track_id.split("&")[0]
                        ytm_uris.append(ytm_track_id.split("=")[-1])
                        mb_uris.append(raw["id"])

    df = pd.DataFrame({"spotify": sp_uris, "ytm": ytm_uris, "mb": mb_uris})
    df.to_csv("dataset.csv", index=False)

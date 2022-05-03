from universal_playlists.main import get_prediction_uri, service_factory
from universal_playlists.services.services import *
import os
import pandas as pd
from tqdm import tqdm
from universal_playlists.types import EntityType

from universal_playlists.uri import URI_Builder


class Evaluator:
    def __init__(self, dataset_path: Path):
        self.df = pd.read_csv(dataset_path)
        headers = self.df.columns.values
        header_servicetype_map = {
            "spotify": ServiceType.SPOTIFY,
            "ytm": ServiceType.YTM,
            "mb": ServiceType.MB,
        }

        service_types = [header_servicetype_map[header] for header in headers]
        self.services = {
            service_type.value: service_factory(
                service_type,
                service_type.value,
                config_path=Path("data/service_configs")
                / f"{service_type.name}_config.json",
            )
            for service_type in service_types
        }

    def evaluate(
        self,
        source_service_type: ServiceType,
        target_service_type: ServiceType,
        n=10,
        verbose=False,
    ):
        source_service = self.services[source_service_type.value]
        target_service = self.services[target_service_type.value]

        source_header = source_service_type.name.lower()
        target_header = target_service_type.name.lower()

        source_uris = [
            URI_Builder(source_service_type, EntityType.TRACK, uri)
            for uri in self.df[source_header]
        ][:n]
        target_uris = [
            URI_Builder(target_service_type, EntityType.TRACK, uri)
            for uri in self.df[target_header]
        ][:n]
        prediction_uris = [
            get_prediction_uri(source_service, target_service, source_uri)
            for source_uri in tqdm(source_uris)
        ]

        correct = len(
            [
                target_uri
                for target_uri, prediction_uri in zip(target_uris, prediction_uris)
                if target_uri == prediction_uri
            ]
        )

        print(f"{correct}/{n} correct")
        num_none = len(
            [
                prediction_uri
                for prediction_uri in prediction_uris
                if prediction_uri is None
            ]
        )
        print(f"{num_none}/{n} predictions were None")

        if verbose:
            for p, t, s in zip(prediction_uris, target_uris, source_uris):
                if p != t and p and t:
                    print(f"Source: {s.url()} Prediction: {p.url()} Target: {t.url()}")


def main():
    os.chdir(Path(__file__).parent)

    evaluator = Evaluator(Path("data") / "dataset.csv")
    evaluator.evaluate(ServiceType.YTM, ServiceType.SPOTIFY, n=100)
    evaluator.evaluate(ServiceType.SPOTIFY, ServiceType.YTM, n=100)
    evaluator.evaluate(ServiceType.SPOTIFY, ServiceType.MB, n=100)

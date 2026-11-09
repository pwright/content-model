"""Load mappings.yaml into a SQLite database using the generated SQLAlchemy models."""

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, ContentMapping, ContentProvenanceDatabase, DownstreamTopic, UpstreamTopic


def load(db_path: str = "provenance.db", data_path: str = "mappings.yaml") -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with open(data_path) as f:
        data = yaml.safe_load(f)

    with Session(engine) as session:
        root = ContentProvenanceDatabase()
        session.add(root)
        session.flush()

        upstream_by_id: dict[str, UpstreamTopic] = {}
        for rec in data.get("upstream_topics", []):
            topic = UpstreamTopic(
                id=rec["id"],
                path=rec.get("path"),
                anchor=rec.get("anchor"),
                title=rec.get("title"),
                content_type=rec.get("content_type"),
                source_category=rec.get("source_category"),
                status=rec.get("status"),
                ContentProvenanceDatabase_id=root.id,
            )
            session.add(topic)
            upstream_by_id[topic.id] = topic

        downstream_by_id: dict[str, DownstreamTopic] = {}
        for rec in data.get("downstream_topics", []):
            topic = DownstreamTopic(
                id=rec["id"],
                dam_path=rec.get("dam_path"),
                title=rec.get("title"),
                dita_type=rec.get("dita_type"),
                nav_section=rec.get("nav_section"),
                ContentProvenanceDatabase_id=root.id,
            )
            session.add(topic)
            downstream_by_id[topic.id] = topic

        for rec in data.get("mappings", []):
            mapping = ContentMapping(
                upstream_id=rec.get("upstream"),
                downstream_id=rec.get("downstream"),
                derivation_type=rec["derivation_type"],
                ContentProvenanceDatabase_id=root.id,
            )
            session.add(mapping)

        session.commit()

    up = len(upstream_by_id)
    down = len(downstream_by_id)
    maps = len(data.get("mappings", []))
    print(f"Loaded {up} upstream, {down} downstream, {maps} mappings into {db_path}")


if __name__ == "__main__":
    load()

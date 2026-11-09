from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    Time,
)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


metadata = Base.metadata


class ContentProvenanceDatabase(Base):
    """
    Root container for all content provenance data.
    """

    __tablename__ = "ContentProvenanceDatabase"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)

    # One-To-Many: OneToAnyMapping(source_class='ContentProvenanceDatabase', source_slot='upstream_topics', mapping_type=None, target_class='UpstreamTopic', target_slot='ContentProvenanceDatabase_id', join_class=None, uses_join_table=None, multivalued=False)
    upstream_topics: Mapped[list[UpstreamTopic]] = relationship(foreign_keys="[UpstreamTopic.ContentProvenanceDatabase_id]")

    # One-To-Many: OneToAnyMapping(source_class='ContentProvenanceDatabase', source_slot='downstream_topics', mapping_type=None, target_class='DownstreamTopic', target_slot='ContentProvenanceDatabase_id', join_class=None, uses_join_table=None, multivalued=False)
    downstream_topics: Mapped[list[DownstreamTopic]] = relationship(foreign_keys="[DownstreamTopic.ContentProvenanceDatabase_id]")

    # One-To-Many: OneToAnyMapping(source_class='ContentProvenanceDatabase', source_slot='mappings', mapping_type=None, target_class='ContentMapping', target_slot='ContentProvenanceDatabase_id', join_class=None, uses_join_table=None, multivalued=False)
    mappings: Mapped[list[ContentMapping]] = relationship(foreign_keys="[ContentMapping.ContentProvenanceDatabase_id]")

    def __repr__(self):
        return f"ContentProvenanceDatabase(id={self.id},)"


class UpstreamTopic(Base):
    """
    A content unit in the upstream Skupper community docs. May represent a whole Markdown file or a section within one, identified by anchor.
    """

    __tablename__ = "UpstreamTopic"

    id: Mapped[str] = mapped_column(Text(), primary_key=True)
    path: Mapped[str] = mapped_column(Text())
    anchor: Mapped[str | None] = mapped_column(Text())
    title: Mapped[str | None] = mapped_column(Text())
    content_type: Mapped[str | None] = mapped_column(Enum('ASSEMBLY', 'CONCEPT', 'TASK', 'REFERENCE', name='UpstreamContentType'))
    source_category: Mapped[str] = mapped_column(Enum('guide', 'reference', name='SourceCategory'))
    status: Mapped[str | None] = mapped_column(Enum('draft', 'stable', 'needs_work', name='ContentStatus'))
    ContentProvenanceDatabase_id: Mapped[int | None] = mapped_column(Integer(), ForeignKey("ContentProvenanceDatabase.id"))

    def __repr__(self):
        return f"UpstreamTopic(id={self.id},path={self.path},anchor={self.anchor},title={self.title},content_type={self.content_type},source_category={self.source_category},status={self.status},ContentProvenanceDatabase_id={self.ContentProvenanceDatabase_id},)"


class DownstreamTopic(Base):
    """
    A DITA topic in the downstream RHSI docs (AEM). Identified by its stable GUID; the DAM path is a human-readable label.
    """

    __tablename__ = "DownstreamTopic"

    id: Mapped[str] = mapped_column(Text(), primary_key=True)
    dam_path: Mapped[str | None] = mapped_column(Text())
    title: Mapped[str | None] = mapped_column(Text())
    dita_type: Mapped[str | None] = mapped_column(Enum('concept', 'task', 'reference', name='DitaTopicType'))
    nav_section: Mapped[str | None] = mapped_column(Enum('discover', 'plan', 'install', 'deploy', 'configure', 'secure', 'observe', 'troubleshoot', 'upgrade', 'reference', 'whats-new', 'pdfs', name='NavSection'))
    ContentProvenanceDatabase_id: Mapped[int | None] = mapped_column(Integer(), ForeignKey("ContentProvenanceDatabase.id"))

    def __repr__(self):
        return f"DownstreamTopic(id={self.id},dam_path={self.dam_path},title={self.title},dita_type={self.dita_type},nav_section={self.nav_section},ContentProvenanceDatabase_id={self.ContentProvenanceDatabase_id},)"


class ContentMapping(Base):
    """
    A provenance relationship between one upstream content unit and one downstream topic. Always 1:1; fan-out and fan-in are expressed as multiple mapping records.
    """

    __tablename__ = "ContentMapping"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    derivation_type: Mapped[str] = mapped_column(Enum('direct_port', 'rewritten', 'restructured', 'downstream_only', 'upstream_only', 'shared_source', name='DerivationType'))
    ContentProvenanceDatabase_id: Mapped[int | None] = mapped_column(Integer(), ForeignKey("ContentProvenanceDatabase.id"))
    upstream_id: Mapped[str | None] = mapped_column(Text(), ForeignKey("UpstreamTopic.id"))
    upstream: Mapped[UpstreamTopic | None] = relationship(foreign_keys=[upstream_id])
    downstream_id: Mapped[str | None] = mapped_column(Text(), ForeignKey("DownstreamTopic.id"))
    downstream: Mapped[DownstreamTopic | None] = relationship(foreign_keys=[downstream_id])

    def __repr__(self):
        return f"ContentMapping(id={self.id},derivation_type={self.derivation_type},ContentProvenanceDatabase_id={self.ContentProvenanceDatabase_id},upstream_id={self.upstream_id},downstream_id={self.downstream_id},)"


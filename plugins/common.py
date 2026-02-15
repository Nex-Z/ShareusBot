from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import Settings
from shared.services.alist_service import AlistService
from shared.services.archive_service import ArchiveService
from shared.services.blacklist_service import BlackListService
from shared.services.file_processor_service import FileProcessorService
from shared.services.meilisearch_service import MeiliSearchService
from shared.services.nonsense_service import NonsenseService
from shared.services.q_member_service import QMemberService
from shared.services.qq_info_service import QQInfoService
from shared.services.query_log_service import QueryLogService
from shared.services.r2_service import R2Service
from shared.services.short_url_service import ShortUrlService


@dataclass
class AppContext:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    _alist_service: AlistService | None = None
    _blacklist_service: BlackListService | None = None
    _archive_service: ArchiveService | None = None
    _file_processor_service: FileProcessorService | None = None
    _query_log_service: QueryLogService | None = None
    _nonsense_service: NonsenseService | None = None
    _q_member_service: QMemberService | None = None
    _qq_info_service: QQInfoService | None = None
    _meilisearch_service: MeiliSearchService | None = None
    _r2_service: R2Service | None = None
    _short_url_service: ShortUrlService | None = None

    def blacklist_service(self) -> BlackListService:
        if self._blacklist_service is None:
            self._blacklist_service = BlackListService(self.session_factory)
        return self._blacklist_service

    def alist_service(self) -> AlistService:
        if self._alist_service is None:
            self._alist_service = AlistService(self.settings)
        return self._alist_service

    def archive_service(self) -> ArchiveService:
        if self._archive_service is None:
            self._archive_service = ArchiveService(self.session_factory)
        return self._archive_service

    def query_log_service(self) -> QueryLogService:
        if self._query_log_service is None:
            self._query_log_service = QueryLogService(self.session_factory)
        return self._query_log_service

    def nonsense_service(self) -> NonsenseService:
        if self._nonsense_service is None:
            self._nonsense_service = NonsenseService(self.session_factory, self.settings)
        return self._nonsense_service

    def q_member_service(self) -> QMemberService:
        if self._q_member_service is None:
            self._q_member_service = QMemberService(self.session_factory)
        return self._q_member_service

    def qq_info_service(self) -> QQInfoService:
        if self._qq_info_service is None:
            self._qq_info_service = QQInfoService(self.settings)
        return self._qq_info_service

    def file_processor_service(self) -> FileProcessorService:
        if self._file_processor_service is None:
            self._file_processor_service = FileProcessorService(self.settings)
        return self._file_processor_service

    def meilisearch_service(self) -> MeiliSearchService:
        if self._meilisearch_service is None:
            self._meilisearch_service = MeiliSearchService(self.settings)
        return self._meilisearch_service

    def r2_service(self) -> R2Service:
        if self._r2_service is None:
            self._r2_service = R2Service(self.settings)
        return self._r2_service

    def short_url_service(self) -> ShortUrlService:
        if self._short_url_service is None:
            self._short_url_service = ShortUrlService(self.settings)
        return self._short_url_service

from __future__ import annotations

from typing import Optional

from app.models.configuration import get_exai_logger
from app.models.orchestrator.ai.oracle_ai_orchestrator import (
    OracleAIOrchestrator,
    OracleAIResponse,
)


logger = get_exai_logger(__name__)


class OracleAICoordinator:
    """
    Request-facing coordinator for Oracle AI questions.

    This class gives Flask routes, CLI scripts, or tests one clean method
    to call without knowing the details of schema summaries, AI prompting,
    or SQL execution.

    Responsibility:
        - Accept a user-facing question.
        - Validate/normalize the question.
        - Pass the request to OracleAIOrchestrator.
        - Return the orchestrator response.

    This class should not:
        - Generate SQL directly.
        - Execute SQL directly.
        - Build schema summaries directly.
        - Call the AI provider directly.
    """

    def __init__(
        self,
        orchestrator: Optional[OracleAIOrchestrator] = None,
    ) -> None:
        self.orchestrator = orchestrator or OracleAIOrchestrator()

        logger.debug(
            "OracleAICoordinator initialized. orchestrator=%s",
            type(self.orchestrator).__name__,
        )

    def ask(
        self,
        question: str,
    ) -> OracleAIResponse:
        """
        Ask a natural-language question about the configured Oracle database.

        Args:
            question:
                Natural-language database question from the user.

        Returns:
            OracleAIResponse
        """
        clean_question = self._normalize_question(question)

        logger.info(
            "Oracle AI coordinator received question. question=%s",
            clean_question,
        )

        if not clean_question:
            logger.warning("Oracle AI coordinator received an empty question.")

            return OracleAIResponse(
                success=False,
                question=question or "",
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="No question was provided.",
                schema_owner=getattr(self.orchestrator, "schema_owner", "UNKNOWN"),
                error="Empty question",
            )

        try:
            response = self.orchestrator.answer_question(clean_question)

            logger.info(
                "Oracle AI coordinator completed question. success=%s row_count=%s command_type=%s",
                response.success,
                response.row_count,
                response.sql_command_type,
            )

            if response.error:
                logger.warning(
                    "Oracle AI coordinator response contained error. error=%s",
                    response.error,
                )

            return response

        except Exception as exc:
            logger.exception(
                "Oracle AI coordinator failed while asking question."
            )

            return OracleAIResponse(
                success=False,
                question=clean_question,
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="The Oracle AI coordinator failed while processing the question.",
                schema_owner=getattr(self.orchestrator, "schema_owner", "UNKNOWN"),
                error=str(exc),
            )

    def ask_with_options(
        self,
        question: str,
        include_sample_rows: bool = True,
        max_tables: int = 50,
        max_result_rows: int = 100,
    ) -> OracleAIResponse:
        """
        Ask a natural-language question with runtime options.

        This is useful for tests, CLI tools, and future Flask routes where you
        may want to control how much schema context or result data is used.

        Args:
            question:
                Natural-language database question from the user.

            include_sample_rows:
                Whether schema summaries should include sample rows.

            max_tables:
                Maximum number of tables to include in schema context.

            max_result_rows:
                Maximum number of SQL result rows to return.

        Returns:
            OracleAIResponse
        """
        clean_question = self._normalize_question(question)

        logger.info(
            "Oracle AI coordinator received question with options. "
            "question=%s include_sample_rows=%s max_tables=%s max_result_rows=%s",
            clean_question,
            include_sample_rows,
            max_tables,
            max_result_rows,
        )

        if not clean_question:
            logger.warning(
                "Oracle AI coordinator received an empty question with options."
            )

            return OracleAIResponse(
                success=False,
                question=question or "",
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="No question was provided.",
                schema_owner=getattr(self.orchestrator, "schema_owner", "UNKNOWN"),
                error="Empty question",
            )

        try:
            response = self.orchestrator.answer_question(
                question=clean_question,
                include_sample_rows=include_sample_rows,
                max_tables=max_tables,
                max_result_rows=max_result_rows,
            )

            logger.info(
                "Oracle AI coordinator completed question with options. "
                "success=%s row_count=%s command_type=%s",
                response.success,
                response.row_count,
                response.sql_command_type,
            )

            if response.error:
                logger.warning(
                    "Oracle AI coordinator response contained error. error=%s",
                    response.error,
                )

            return response

        except Exception as exc:
            logger.exception(
                "Oracle AI coordinator failed while asking question with options."
            )

            return OracleAIResponse(
                success=False,
                question=clean_question,
                generated_sql=None,
                sql_command_type=None,
                rows=[],
                row_count=0,
                explanation="The Oracle AI coordinator failed while processing the question.",
                schema_owner=getattr(self.orchestrator, "schema_owner", "UNKNOWN"),
                error=str(exc),
            )

    @staticmethod
    def _normalize_question(question: str) -> str:
        """
        Normalize the incoming user question.

        Args:
            question:
                Raw user question.

        Returns:
            Cleaned question string.
        """
        if question is None:
            return ""

        return str(question).strip()
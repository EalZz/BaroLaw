package com.example.barolaw

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * LegalResponseParser의 파싱 로직을 검증하는 단위 테스트
 */
class LegalResponseParserTest {

    @Test
    fun `extractLawDetails - 정상 JSON 배열 파싱`() {
        val content = """
            답변 내용...
            ---[LEGAL_DETAILS]---
            [
                {"title": "민법 제1조", "content": "민사에 관하여 법률에 규정이 없으면 관습법에 의하고..."},
                {"title": "민법 제2조", "content": "권리의 행사와 의무의 이행은 신의에 좇아 성실히 하여야 한다."}
            ]
        """.trimIndent()
        
        val details = LegalResponseParser.extractLawDetails(content)
        
        assertEquals(2, details.size)
        assertEquals("민법 제1조", details[0].title)
        assertEquals("민사에 관하여 법률에 규정이 없으면 관습법에 의하고...", details[0].content)
        assertEquals("민법 제2조", details[1].title)
    }

    @Test
    fun `extractLawDetails - 닫히지 않은 JSON은 빈 리스트 반환`() {
        val content = """
            ---[LEGAL_DETAILS]---
            [
                {"title": "민법 제1조", "content": "문장이 아직...
        """.trimIndent()
        
        val details = LegalResponseParser.extractLawDetails(content)
        
        // 스트리밍 중 데이터가 짤린 경우 크래시 없이 빈 리스트를 반환해야 함
        assertTrue("닫히지 않은 JSON은 빈 리스트를 반환해야 합니다.", details.isEmpty())
    }

    @Test
    fun `extractLawDetails - 태그가 없으면 빈 리스트 반환`() {
        val content = "일반적인 답변 텍스트입니다."
        
        val details = LegalResponseParser.extractLawDetails(content)
        
        assertTrue(details.isEmpty())
    }

    @Test
    fun `extractDisplaySections - LEGAL_BASIS 앞 본문 추출`() {
        val content = """
            이것은 본문입니다.
            ---[LEGAL_BASIS]---
            - 근거 1
        """.trimIndent()
        
        val sections = LegalResponseParser.extractDisplaySections(content)
        
        assertEquals("이것은 본문입니다.", sections.mainBody)
        assertEquals("- 근거 1", sections.legalBasis)
    }

    @Test
    fun `extractDisplaySections - ASSISTANT_ANSWER가 있으면 그 뒤 본문 우선`() {
        val content = """
            ---[RAG_ENGINE_RESULT]---
            엔진 결과...
            ---[ASSISTANT_ANSWER]---
            사용자에게 보여줄 진짜 본문입니다.
            ---[LEGAL_BASIS]---
            - 근거...
        """.trimIndent()
        
        val sections = LegalResponseParser.extractDisplaySections(content)
        
        // ANSWER 태그가 있으면 그 앞의 엔진 결과 등은 무시하고 본문으로 추출해야 함
        assertEquals("사용자에게 보여줄 진짜 본문입니다.", sections.mainBody)
    }

    @Test
    fun `extractDisplaySections - 불렛 형태만 legalBasisItems로 추출`() {
        val content = """
            본문...
            ---[LEGAL_BASIS]---
            참고한 법령은 다음과 같습니다.
            - 민법 제1조
            - 형법 제10조
            기타 참고사항
            ---[LEGAL_DETAILS]---
            [...]
        """.trimIndent()
        
        val sections = LegalResponseParser.extractDisplaySections(content)
        
        // "참고한 법령은 다음과 같습니다."와 "기타 참고사항", 태그 라인은 제외되어야 함
        assertEquals(2, sections.legalBasisItems.size)
        assertEquals("- 민법 제1조", sections.legalBasisItems[0])
        assertEquals("- 형법 제10조", sections.legalBasisItems[1])
    }

    @Test
    fun `extractDisplaySections - 태그가 없으면 전체 내용을 본문으로 유지`() {
        val content = "일반적인 답변 텍스트입니다."

        val sections = LegalResponseParser.extractDisplaySections(content)

        // 태그가 없을 때 원본 텍스트가 모두 메인 바디로 유지되는지 확인 (Task 2-5 목적)
        assertEquals("일반적인 답변 텍스트입니다.", sections.mainBody)
        assertEquals("", sections.legalBasis)
        assertTrue(sections.legalBasisItems.isEmpty())
    }

    @Test
    fun `extractFallbackLawDetails - 법적 근거 bullet을 제목 전용 LawDetail로 변환`() {
        val content = """
            본문...
            ---[LEGAL_BASIS]---
            참고한 법령은 다음과 같습니다.
            - 민법 제1조
            - 형법 제10조
            기타 참고사항
        """.trimIndent()

        val details = LegalResponseParser.extractFallbackLawDetails(
            content = content,
            fallbackMessage = "상세 내용은 백엔드에서 불러오지 못했습니다."
        )

        assertEquals(2, details.size)
        assertEquals("민법 제1조", details[0].title)
        assertEquals("상세 내용은 백엔드에서 불러오지 못했습니다.", details[0].content)
        assertEquals("형법 제10조", details[1].title)
    }
}

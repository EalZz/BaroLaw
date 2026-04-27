package com.example.barolaw

import org.json.JSONArray
import org.json.JSONObject
import com.example.barolaw.model.*


/**
 * 응답 섹션별 데이터를 담는 데이터 클래스
 */
data class LegalDisplaySections(
    val mainBody: String,
    val legalBasis: String,
    val legalBasisItems: List<String>
)

/**
 * 백엔드 SSE 응답 문자열에서 법령 상세 정보 및 화면 표시용 섹션을 추출하는 파서
 */
object LegalResponseParser {
    const val DETAILS_TAG = "---[LEGAL_DETAILS]---"
    const val BASIS_TAG = "---[LEGAL_BASIS]---"
    const val ANSWER_TAG = "---[ASSISTANT_ANSWER]---"

    /**
     * 누적 응답 문자열에서 [LawDetail] 목록을 추출합니다.
     * 스트리밍 중인 불완전한 JSON의 경우 예외를 발생시키지 않고 빈 리스트를 반환합니다.
     */
    fun extractLawDetails(content: String): List<LawDetail> {
        if (!content.contains(DETAILS_TAG)) return emptyList()
        
        return try {
            val extracted = content.substringAfter(DETAILS_TAG, "")
            val startIndex = extracted.indexOf('[')
            val endIndex = extracted.lastIndexOf(']')
            
            if (startIndex != -1 && endIndex != -1 && endIndex > startIndex) {
                val cleanJson = extracted.substring(startIndex, endIndex + 1)
                val jsonArray = JSONArray(cleanJson)
                val details = mutableListOf<LawDetail>()
                
                for (i in 0 until jsonArray.length()) {
                    val obj = jsonArray.optJSONObject(i)
                    if (obj != null) {
                        val title = obj.optString("title").trim()
                        val lawContent = obj.optString("content").trim()
                        if (title.isNotEmpty()) {
                            details.add(LawDetail(title, lawContent.ifEmpty { "상세 정보가 없습니다." }))
                        }
                    }
                }
                details
            } else {
                emptyList()
            }
        } catch (e: Exception) {
            // 파싱 중(데이터 미완성)일 때는 빈 리스트 반환
            emptyList()
        }
    }

    /**
     * 누적 응답 문자열에서 본문과 법적 근거 섹션을 분리하여 추출합니다.
     */
    fun extractDisplaySections(content: String): LegalDisplaySections {
        // 1. 본문(Main Body) 추출: ANSWER 태그가 있으면 그 뒤를, 없으면 BASIS/DETAILS 태그 앞을 사용
        val mainBody = when {
            content.contains(ANSWER_TAG) -> {
                content.substringAfter(ANSWER_TAG)
                    .substringBefore(BASIS_TAG)
                    .substringBefore(DETAILS_TAG)
                    .trim()
            }
            else -> {
                content.substringBefore(BASIS_TAG)
                    .substringBefore(DETAILS_TAG)
                    .trim()
            }
        }

        // 2. 법적 근거(Legal Basis) 텍스트 추출
        val legalBasis = if (content.contains(BASIS_TAG)) {
            content.substringAfter(BASIS_TAG)
                .substringBefore(DETAILS_TAG)
                .substringBefore(ANSWER_TAG)
                .trim()
        } else ""

        // 3. 법적 근거 목록(Items) 추출
        // 규칙: trim() 결과가 "-"로 시작하고 "---"로 시작하지 않는 줄만 추출
        val legalBasisItems = if (legalBasis.isNotEmpty()) {
            legalBasis.split("\n")
                .map { it.trim() }
                .filter { it.startsWith("-") && !it.startsWith("---") }
        } else emptyList()

        return LegalDisplaySections(
            mainBody = mainBody,
            legalBasis = legalBasis,
            legalBasisItems = legalBasisItems
        )
    }

    /**
     * LEGAL_DETAILS JSON이 없거나 아직 파싱되지 않은 경우, 법적 근거 bullet을
     * 제목 전용 [LawDetail] 목록으로 변환합니다.
     */
    fun extractFallbackLawDetails(content: String, fallbackMessage: String): List<LawDetail> {
        val sections = extractDisplaySections(content)

        return sections.legalBasisItems
            .map { it.removePrefix("-").trim() }
            .filter { it.isNotEmpty() && !it.contains("국가 법령") }
            .map { title -> LawDetail(title, fallbackMessage) }
    }
}

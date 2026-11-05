package kr.ac.baekseok.semesh

import android.os.Bundle
import android.widget.Button
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

// 가이드 화면: 주제 버튼을 누르면 AlertDialog로 설명을 띄운다 (수업 DialogBox 예제 방식)
class GuideActivity : AppCompatActivity() {

    private lateinit var btnTypes: Button
    private lateinit var btnSteps: Button
    private lateinit var btnSupport: Button
    private lateinit var btnGuideBack: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_guide)
        title = getString(R.string.title_guide)

        btnTypes = findViewById(R.id.btnTypes)
        btnSteps = findViewById(R.id.btnSteps)
        btnSupport = findViewById(R.id.btnSupport)
        btnGuideBack = findViewById(R.id.btnGuideBack)

        // TODO(4주차): 아래 문구는 뼈대용 요약. 지난 학기 웹(prevention.html, support.html) 내용과
        //              공식 자료(HUG, 국토부 전세사기 피해지원) 기준으로 다듬고 출처를 붙인다.
        btnTypes.setOnClickListener {
            showGuide(
                "전세사기 유형",
                "· 깡통전세: 보증금이 집값과 비슷하거나 더 높아 돌려받기 어려운 경우\n\n" +
                "· 이중계약: 한 집을 여러 사람과 계약하거나 가짜 계약서를 쓰는 경우\n\n" +
                "· 신탁사기: 소유권이 신탁회사에 있는데 집주인이 몰래 계약하는 경우\n\n" +
                "· 무자본 갭투자: 보증금으로 집을 여러 채 사들인 뒤 돌려주지 못하는 경우"
            )
        }
        btnSteps.setOnClickListener {
            showGuide(
                "계약 전 4단계 점검",
                "1. 시세 확인: 전세가율이 너무 높지 않은지\n\n" +
                "2. 등기부등본: 소유자, 근저당, 압류·가압류, 신탁 여부\n\n" +
                "3. 집주인 확인: 신분증, 세금 체납 여부\n\n" +
                "4. 계약 후: 전입신고·확정일자, 전세보증금반환보증 가입"
            )
        }
        btnSupport.setOnClickListener {
            showGuide(
                "피해 시 지원",
                "· 전세피해지원센터 상담\n\n" +
                "· 경매·공매 지원 서비스 (HUG)\n\n" +
                "· 법률 상담 (대한법률구조공단 등)\n\n" +
                "· 긴급 주거·금융 지원\n\n" +
                "(연락처·신청 방법은 추가 예정)"
            )
        }

        btnGuideBack.setOnClickListener {
            finish()
        }
    }//onCreate()

    // 제목과 내용을 받아 대화상자를 띄우는 함수 (버튼 3개가 같은 코드를 쓰도록 하나로 묶음)
    fun showGuide(title: String, message: String) {
        val dlg = AlertDialog.Builder(this)
        dlg.setTitle(title)
        dlg.setMessage(message)
        dlg.setPositiveButton("닫기", null)
        dlg.show()
    }
}//GuideActivity

package kr.ac.baekseok.semesh

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

// 안전 진단 화면: 1 기본 정보 → 2 자가 점검 → 3 계약서 체크 → 4 결과
class DiagnosisActivity : AppCompatActivity() {

    private lateinit var tvStep: TextView
    private lateinit var pbStep: ProgressBar
    private lateinit var btnPrev: Button
    private lateinit var btnNext: Button

    // 1단계 입력
    private lateinit var rgHouseType: RadioGroup
    private lateinit var edtDeposit: EditText
    private lateinit var edtPrice: EditText

    // 4단계 결과
    private lateinit var tvResult: TextView

    // 단계별 묶음(LinearLayout)을 배열에 넣어 두면 번호(0~3)로 쉽게 보이기/숨기기 할 수 있다
    private lateinit var steps: Array<LinearLayout>
    private val stepNames = arrayOf("기본 정보", "자가 점검", "계약서 체크", "결과")

    // 2·3단계 체크박스 전체 (결과 계산 때 몇 개 체크했는지 셀 때 사용)
    private lateinit var checks: Array<CheckBox>

    private var current = 0 // 지금 보고 있는 단계 (0부터 시작)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_diagnosis)
        title = getString(R.string.title_diagnosis)

        tvStep = findViewById(R.id.tvStep)
        pbStep = findViewById(R.id.pbStep)
        btnPrev = findViewById(R.id.btnPrev)
        btnNext = findViewById(R.id.btnNext)
        rgHouseType = findViewById(R.id.rgHouseType)
        edtDeposit = findViewById(R.id.edtDeposit)
        edtPrice = findViewById(R.id.edtPrice)
        tvResult = findViewById(R.id.tvResult)

        steps = arrayOf(
            findViewById(R.id.step1), findViewById(R.id.step2),
            findViewById(R.id.step3), findViewById(R.id.step4)
        )
        checks = arrayOf(
            findViewById(R.id.chkRegistry), findViewById(R.id.chkOwner),
            findViewById(R.id.chkTax), findViewById(R.id.chkInsurance),
            findViewById(R.id.chkAgent), findViewById(R.id.chkAccount),
            findViewById(R.id.chkSpecial), findViewById(R.id.chkMoveIn)
        )

        showStep(0)

        btnPrev.setOnClickListener {
            if (current == 0) {
                finish() // 첫 단계에서 [뒤로]를 누르면 메인으로
            } else {
                showStep(current - 1)
            }
        }

        btnNext.setOnClickListener {
            when (current) {
                0 -> {
                    // 1단계는 입력이 비어 있으면 다음으로 넘어가지 않음
                    if (!checkStep1()) return@setOnClickListener
                    showStep(1)
                }
                1 -> showStep(2)
                2 -> {
                    makeResult()  // 결과 문장을 만든 뒤
                    showStep(3)   // 결과 화면으로
                }
                3 -> finish()     // 결과 화면에서는 [홈으로]
            }
        }
    }//onCreate()

    // n번째 단계만 보이고 나머지는 숨긴다. 버튼 글자와 진행바도 함께 바꾼다.
    fun showStep(n: Int) {
        current = n
        for (i in steps.indices) {
            steps[i].visibility = if (i == n) View.VISIBLE else View.GONE
        }
        tvStep.text = "${n + 1} / 4  ${stepNames[n]}"
        pbStep.progress = n + 1
        btnPrev.text = if (n == 0) getString(R.string.btn_back) else getString(R.string.btn_prev)
        btnNext.text = if (n == 3) getString(R.string.btn_home) else getString(R.string.btn_next)
    }

    // 1단계 입력값 검사: 주택 유형 선택 + 숫자 2개 입력
    fun checkStep1(): Boolean {
        if (rgHouseType.checkedRadioButtonId == -1) {
            Toast.makeText(applicationContext, "주택 유형을 선택하세요", Toast.LENGTH_SHORT).show()
            return false
        }
        if (edtDeposit.text.isEmpty() || edtPrice.text.isEmpty()) {
            Toast.makeText(applicationContext, "보증금과 시세를 모두 입력하세요", Toast.LENGTH_SHORT).show()
            return false
        }
        return true
    }

    // 결과 만들기
    // TODO: 판정 기준(전세가율 몇 % 이상이 위험인지, 체크 항목 가중치)은 자료 조사 후 확정.
    //       지금은 화면 흐름 확인용으로 "전세가율"과 "체크 안 한 항목 수"만 보여준다.
    fun makeResult() {
        val deposit = edtDeposit.text.toString().toDouble()
        val price = edtPrice.text.toString().toDouble()

        // 전세가율 = 보증금 ÷ 매매 시세 × 100. 높을수록 집값이 떨어졌을 때 보증금을 못 돌려받을 위험이 큼
        val ratio = if (price > 0) deposit / price * 100 else 0.0

        var missing = ""   // 체크 안 한 항목 목록
        var missingCount = 0
        for (chk in checks) {
            if (!chk.isChecked) {
                missing += "· ${chk.text}\n"
                missingCount++
            }
        }

        var result = "전세가율: ${"%.1f".format(ratio)}%\n"
        result += "확인하지 않은 항목: ${missingCount}개 / ${checks.size}개\n\n"
        if (missingCount > 0) {
            result += "다시 확인해 보세요\n$missing"
        } else {
            result += "모든 항목을 확인했어요"
        }
        // TODO(3주차): 메인 화면에서 찾은 내 지역 위험등급도 결과에 함께 표시
        tvResult.text = result
    }
}//DiagnosisActivity

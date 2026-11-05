package kr.ac.baekseok.semesh

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

// 첫 화면: 내 위치의 위험도 카드 + 다른 화면으로 가는 메뉴 버튼 3개
class MainActivity : AppCompatActivity() {

    // 위젯 변수 선언 (onCreate에서 findViewById로 초기화하므로 lateinit)
    private lateinit var tvLocation: TextView
    private lateinit var tvRegion: TextView
    private lateinit var tvGrade: TextView
    private lateinit var tvDetail: TextView
    private lateinit var btnLocation: Button
    private lateinit var btnMap: Button
    private lateinit var btnDiagnosis: Button
    private lateinit var btnGuide: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        title = getString(R.string.title_main)

        // UI 위젯 연결
        tvLocation = findViewById(R.id.tvLocation)
        tvRegion = findViewById(R.id.tvRegion)
        tvGrade = findViewById(R.id.tvGrade)
        tvDetail = findViewById(R.id.tvDetail)
        btnLocation = findViewById(R.id.btnLocation)
        btnMap = findViewById(R.id.btnMap)
        btnDiagnosis = findViewById(R.id.btnDiagnosis)
        btnGuide = findViewById(R.id.btnGuide)

        // [내 위치로 확인하기]
        // TODO(3주차): GPS로 위도·경도 → 시군구 이름 → SQLite(regionTBL)에서 등급 조회
        // 지금은 화면 흐름만 확인하려고 임시 값을 넣어 둔다.
        // (건수는 region_merged.csv의 서울 중구 값, 등급은 03단계 분석이 끝나야 정해짐)
        btnLocation.setOnClickListener {
            showRegion("서울", "중구", "계산 전", 51, 4)
            Toast.makeText(applicationContext, "임시 데이터로 표시했어요 (GPS는 3주차)", Toast.LENGTH_SHORT).show()
        }

        // 메뉴 버튼: Intent로 다른 화면(Activity)을 연다
        btnMap.setOnClickListener {
            val intent = Intent(applicationContext, MapActivity::class.java)
            startActivity(intent)
        }
        btnDiagnosis.setOnClickListener {
            val intent = Intent(applicationContext, DiagnosisActivity::class.java)
            startActivity(intent)
        }
        btnGuide.setOnClickListener {
            val intent = Intent(applicationContext, GuideActivity::class.java)
            startActivity(intent)
        }
    }//onCreate()

    // 위험도 카드에 지역 정보를 채우는 함수
    // 나중에 DB에서 꺼낸 값을 그대로 넘기면 되도록 매개변수로 받는다.
    fun showRegion(sido: String, sigungu: String, grade: String, damage: Int, accident: Int) {
        tvLocation.text = "$sido $sigungu"
        tvRegion.text = "$sido $sigungu"
        tvGrade.text = "등급: $grade"
        tvDetail.text = "피해주택 누적 ${damage}건 · 최근 보증사고 ${accident}건"
        // TODO(디자인 단계): 등급에 따라 cardRisk 배경색 바꾸기 (고위험=빨강, 주의=주황, 안전=초록)
    }
}//MainActivity

package kr.ac.baekseok.semesh

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Geocoder
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale

// 첫 화면: 내 위치의 위험도 카드 + 다른 화면으로 가는 메뉴 버튼 3개
//
// [내 위치로 확인하기]를 누르면
//   ① 위치 권한 확인 (없으면 사용자에게 허락받기)
//   ② LocationManager로 위도·경도 얻기
//   ③ Geocoder로 위도·경도 → 주소 ("대한민국 서울특별시 강서구 화곡동 …")
//   ④ 주소에서 시도·시군구·동 이름을 뽑아 SQLite(regionTBL, dongTBL)에서 등급 찾기
//   ⑤ 카드에 표시 (등급에 따라 배경색), [지도에서 보기]를 누르면 그 동네로 이동
class MainActivity : AppCompatActivity() {

    // 위젯 변수 선언 (onCreate에서 findViewById로 초기화하므로 lateinit)
    private lateinit var tvLocation: TextView
    private lateinit var tvRegion: TextView
    private lateinit var tvGrade: TextView
    private lateinit var tvDetail: TextView
    private lateinit var cardRisk: LinearLayout
    private lateinit var btnLocation: Button
    private lateinit var btnMap: Button
    private lateinit var btnDiagnosis: Button
    private lateinit var btnGuide: Button

    private lateinit var dbHelper: DBHelper

    // 마지막으로 찾은 내 위치 (지도 화면에 넘겨 줄 값). 아직 못 찾았으면 null
    private var myLat: Double? = null
    private var myLng: Double? = null
    private var myCode: String? = null     // 시군구 코드 (예: "11500")
    private var myDong: String? = null     // 서울이면 동 그룹 이름 (예: "화곡동")

    private val REQ_LOCATION = 100         // 권한 요청 번호 (결과가 돌아올 때 어떤 요청이었는지 구분용)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        title = getString(R.string.title_main)

        // UI 위젯 연결
        tvLocation = findViewById(R.id.tvLocation)
        tvRegion = findViewById(R.id.tvRegion)
        tvGrade = findViewById(R.id.tvGrade)
        tvDetail = findViewById(R.id.tvDetail)
        cardRisk = findViewById(R.id.cardRisk)
        btnLocation = findViewById(R.id.btnLocation)
        btnMap = findViewById(R.id.btnMap)
        btnDiagnosis = findViewById(R.id.btnDiagnosis)
        btnGuide = findViewById(R.id.btnGuide)

        // DB는 처음 사용할 때 만들어진다 (그때 assets의 CSV를 읽어 넣음 → DBHelper.onCreate)
        dbHelper = DBHelper(this)

        // [내 위치로 확인하기]
        btnLocation.setOnClickListener {
            // ① 위치는 '위험 권한'이라 Manifest에 적는 것만으로는 안 되고, 실행 중에 사용자에게 허락받아야 한다
            if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                getMyLocation()
            } else {
                requestPermissions(
                    arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
                    REQ_LOCATION
                )
            }
        }

        // 메뉴 버튼: Intent로 다른 화면(Activity)을 연다
        btnMap.setOnClickListener {
            val intent = Intent(applicationContext, MapActivity::class.java)
            // 내 위치를 찾았으면 지도 화면에 넘겨서 그 동네로 바로 이동하게 한다
            if (myCode != null) {
                intent.putExtra("code", myCode)
                intent.putExtra("dong", myDong)        // 서울이 아니면 null
                intent.putExtra("lat", myLat)
                intent.putExtra("lng", myLng)
            }
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

    // 권한 창에서 사용자가 [허용]/[거부]를 누르면 이 함수가 호출된다
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != REQ_LOCATION) return
        // '대략적인 위치'만 허용해도 시군구·동을 찾는 데는 충분하다 → 하나라도 허용되면 진행
        if (grantResults.any { it == PackageManager.PERMISSION_GRANTED }) {
            getMyLocation()
        } else {
            Toast.makeText(this, "위치 권한이 있어야 내 지역을 찾을 수 있어요", Toast.LENGTH_SHORT).show()
        }
    }

    // ② 위도·경도 얻기
    private fun getMyLocation() {
        val lm = getSystemService(LOCATION_SERVICE) as LocationManager
        // GPS가 꺼져 있으면 와이파이·기지국 위치(NETWORK)를 쓴다. 실내에서는 GPS가 잘 안 잡히기도 한다.
        val provider = when {
            lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
            lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> {
                Toast.makeText(this, "휴대폰 설정에서 위치(GPS)를 켜 주세요", Toast.LENGTH_SHORT).show()
                return
            }
        }
        tvLocation.text = "위치를 찾는 중…"
        // requestLocationUpdates: 위치가 새로 잡힐 때마다 listener를 부른다 → 첫 위치를 받으면 바로 멈춘다.
        //   처음엔 getCurrentLocation(한 번만 받기)을 썼는데, 몇 초 전에 받은 위치를 다시 돌려줘서
        //   에뮬레이터에서 위치를 바꿔도 이전 동네가 나왔다 → 새 위치를 확실히 받는 이 방식으로 바꿈
        val listener = object : LocationListener {
            override fun onLocationChanged(loc: Location) {
                lm.removeUpdates(this)                     // 한 번 받았으면 그만 받기 (배터리 절약)
                handler.removeCallbacksAndMessages(null)   // 아래의 '10초 기다리기' 취소
                toAddress(loc.latitude, loc.longitude)
            }
        }
        try {
            lm.requestLocationUpdates(provider, 0L, 0f, listener, mainLooper)
            // 10초 안에 위치가 안 잡히면(실내 등) 휴대폰이 마지막으로 알던 위치라도 쓴다
            handler.postDelayed({
                lm.removeUpdates(listener)
                val last = lm.getLastKnownLocation(provider)
                if (last != null) {
                    toAddress(last.latitude, last.longitude)
                } else {
                    tvLocation.text = getString(R.string.main_location_none)
                    Toast.makeText(this, "위치를 찾지 못했어요. 잠시 후 다시 눌러 주세요", Toast.LENGTH_SHORT).show()
                }
            }, 10_000L)
        } catch (e: SecurityException) {   // 권한이 도중에 취소된 경우
            Toast.makeText(this, "위치 권한이 없어요", Toast.LENGTH_SHORT).show()
        }
    }

    private val handler = Handler(Looper.getMainLooper())

    // ③ 위도·경도 → 주소 (Geocoder는 인터넷으로 주소를 받아 오므로 결과가 나중에 따로 온다)
    private fun toAddress(lat: Double, lng: Double) {
        Geocoder(this, Locale.KOREA).getFromLocation(lat, lng, 5, object : Geocoder.GeocodeListener {
            override fun onGeocode(addresses: MutableList<android.location.Address>) {
                // 기기·지역마다 주소 칸에 들어오는 값이 달라서, 확인용으로 로그(Logcat)에 모두 찍어 둔다
                addresses.forEach {
                    Log.d("SEMESH", "line=${it.getAddressLine(0)} | admin=${it.adminArea} | locality=${it.locality} " +
                        "| subLocality=${it.subLocality} | thoroughfare=${it.thoroughfare} | feature=${it.featureName}")
                }
                // 주소 후보를 여러 개(최대 5개) 받는다. 첫 번째가 "서울특별시 화곡"처럼 구가 빠진 주소일 때가 있어서
                // (에뮬레이터에서 확인) 후보를 차례로 보고, 동까지 찾은 주소 > 시군구만 찾은 주소 순으로 고른다
                val lines = addresses.mapNotNull { it.getAddressLine(0) }
                // 이 함수는 화면 스레드가 아닌 곳에서 불리므로, 화면을 바꿀 때는 runOnUiThread로 감싼다
                runOnUiThread { pickAddress(lines, lat, lng) }
            }

            override fun onError(errorMessage: String?) {
                runOnUiThread { showNotFound("주소 변환 실패 (인터넷 연결을 확인해 주세요)") }
            }
        })
    }

    // 주소 후보 중 가장 자세히 찾아지는 것 고르기
    private fun pickAddress(lines: List<String>, lat: Double, lng: Double) {
        val results = lines.mapNotNull { matchAddress(it) }
        val best = results.firstOrNull { it.second != null }      // 서울 동까지 찾은 결과
            ?: results.firstOrNull { it.first.sido != "서울" }    // 서울이 아니면 시군구만으로 충분
            ?: results.firstOrNull()                              // 서울인데 동을 못 찾았으면 구라도
        if (best == null) {
            showNotFound("이 지역의 자료를 찾지 못했어요: ${lines.firstOrNull() ?: "주소 없음"}")
            return
        }
        val (region, dong) = best
        myLat = lat; myLng = lng; myCode = region.code; myDong = dong?.dong
        showRegion(region, dong)
    }

    // ④ 주소 문자열 하나 → 시도·시군구·동 → DB 조회. 못 찾으면 null
    //   예) "대한민국 서울특별시 강서구 화곡동 1043"   → 서울 / 강서구 / 화곡동
    //       "대한민국 경기도 수원시 영통구 매탄동 …"   → 경기 / 수원영통구 (DB에는 시와 구를 붙여서 저장)
    private fun matchAddress(line: String): Pair<RegionInfo, DongInfo?>? {
        val tokens = line.split(" ").filter { it.isNotBlank() && it != "대한민국" }
        val sidoIdx = tokens.indexOfFirst { sidoNames(it).isNotEmpty() }
        if (sidoIdx < 0) return null
        val sidoList = sidoNames(tokens[sidoIdx])
        val rest = tokens.drop(sidoIdx + 1)
        val first = rest.getOrElse(0) { "" }
        val second = rest.getOrElse(1) { "" }

        // 시군구 이름 후보 (앞에 있는 것부터 DB에서 찾아본다)
        val candidates = mutableListOf<String>()
        if (first.endsWith("시") && second.endsWith("구")) candidates.add(first.dropLast(1) + second) // 수원시 영통구 → 수원영통구
        candidates.add(NEW_GU_TO_OLD[first] ?: first)
        if ("세종" in sidoList) candidates.add("세종시")   // 세종은 주소에 시군구가 없다

        val region = dbHelper.findRegion(sidoList, candidates) ?: return null

        // 서울이면 동 단위 결과도 찾는다 (동 이름 = '동'으로 끝나거나 '종로5가'처럼 '○가'로 끝나는 단어)
        var dong: DongInfo? = null
        if (region.sido == "서울") {
            val dongName = rest.drop(1).firstOrNull { it.endsWith("동") || Regex("\\d+가$").containsMatchIn(it) }
            if (dongName != null) dong = dbHelper.findDong(region.code, dongName)
        }
        return Pair(region, dong)
    }

    // 주소의 시도 이름 → DB의 시도 이름. 시도가 아닌 단어면 빈 목록
    private fun sidoNames(word: String): List<String> = when {
        word.startsWith("서울") -> listOf("서울")
        word.startsWith("부산") -> listOf("부산")
        word.startsWith("대구") -> listOf("대구")
        word.startsWith("인천") -> listOf("인천")
        word.startsWith("광주광역") -> listOf("광주")
        word.startsWith("대전") -> listOf("대전")
        word.startsWith("울산") -> listOf("울산")
        word.startsWith("세종") -> listOf("세종")
        word.startsWith("경기") -> listOf("경기")
        word.startsWith("강원") -> listOf("강원")
        word.startsWith("충청북") || word == "충북" -> listOf("충북")
        word.startsWith("충청남") || word == "충남" -> listOf("충남")
        word.startsWith("전라북") || word.startsWith("전북") -> listOf("전북")
        // 2026년 7월 광주·전남이 '전남광주통합특별시'로 합쳐졌다. DB는 개편 전 기준이라 두 곳 다 찾아본다
        word.startsWith("전남광주") -> listOf("광주", "전남")
        word.startsWith("전라남") || word == "전남" -> listOf("전남")
        word.startsWith("경상북") || word == "경북" -> listOf("경북")
        word.startsWith("경상남") || word == "경남" -> listOf("경남")
        word.startsWith("제주") -> listOf("제주")
        else -> emptyList()
    }

    // 2026년 7월 행정구역 개편으로 새로 생긴 구 → DB(개편 전 기준)의 구 (analysis/data/README.md 참고)
    private val NEW_GU_TO_OLD = mapOf(
        "서해구" to "서구", "검단구" to "서구",       // 인천 서구가 둘로 나뉨
        "영종구" to "중구", "제물포구" to "중구"      // 제물포구에는 옛 동구 일부도 있지만 대부분 옛 중구
    )

    // ⑤ 위험도 카드에 지역 정보를 채우는 함수
    private fun showRegion(r: RegionInfo, d: DongInfo?) {
        val place = "${r.sido} ${r.sigungu}" + (if (d != null) " ${d.dong}" else "")
        tvLocation.text = place
        tvRegion.text = place

        val sb = StringBuilder()
        sb.append("[${r.sigungu}] ${r.grade} · 전국 255곳 중 ${r.rank}위\n")
        sb.append("피해주택 누적 ${r.damage}건 · 최근 보증사고 월평균 ${"%.1f".format(r.accident)}건")
        if (d != null) {
            tvGrade.text = "등급: ${d.grade} (동 기준)"
            sb.append("\n\n[${d.dong}] 피해율이 전국 평균의 ${"%.1f".format(d.ratio)}배 · 서울 310곳 중 ${d.seoulRank}위\n")
            sb.append("피해주택 ${d.damage}건 / 전세 계약 ${d.contracts}건")
            if (d.lowData) sb.append("\n※ 전세 계약이 적어 같은 구 평균에 가깝게 추정한 값이에요")
        } else {
            tvGrade.text = "등급: ${r.grade}"
        }
        sb.append("\n\n'안전'도 전세사기가 없다는 뜻이 아니라, 다른 지역보다 상대적으로 낮다는 뜻이에요.")
        tvDetail.text = sb.toString()

        // 등급에 따라 카드 배경색 (서울은 동 등급 기준)
        val color = when (d?.grade ?: r.grade) {
            "고위험" -> R.color.risk_high
            "주의" -> R.color.risk_mid
            else -> R.color.risk_low
        }
        cardRisk.setBackgroundColor(getColor(color))
    }

    private fun showNotFound(msg: String) {
        tvLocation.text = getString(R.string.main_location_none)
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
    }
}//MainActivity

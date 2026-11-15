package kr.ac.baekseok.semesh

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity

// 지도 화면: 시군구 위험등급 지도(map.html)를 WebView로 보여준다. 서울은 확대하면 동 단위로 바뀐다.
class MapActivity : AppCompatActivity() {

    private lateinit var webMap: WebView
    private lateinit var btnMapBack: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_map)
        title = getString(R.string.title_map)

        webMap = findViewById(R.id.webMap)
        btnMapBack = findViewById(R.id.btnMapBack)

        // 메인 화면에서 내 위치를 찾았으면 넘어온 값 (못 찾았으면 code가 null → 전국 지도 그대로)
        val code = intent.getStringExtra("code")
        val dong = intent.getStringExtra("dong")
        val lat = intent.getDoubleExtra("lat", 0.0)
        val lng = intent.getDoubleExtra("lng", 0.0)

        // WebViewClient를 지정하지 않으면 링크를 눌렀을 때 외부 브라우저가 열린다 (수업 WebView 예제와 같음)
        // onPageFinished: 지도 페이지가 다 열린 뒤에 호출된다. 그 전에 자바스크립트를 부르면 함수가 아직 없어서 실패한다.
        webMap.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
                if (code == null) return
                // map.html 안에 04_make_map.py가 넣어 둔 자바스크립트 함수를 Kotlin에서 호출
                //   showMyLocation(위도, 경도) : 내 위치에 마커
                //   focusDong('11500', '화곡동') : 서울 동으로 이동 / focusRegion('44131') : 시군구로 이동
                view.evaluateJavascript("showMyLocation($lat, $lng);", null)
                if (dong != null) {
                    view.evaluateJavascript("focusDong('$code', '$dong');", null)
                } else {
                    view.evaluateJavascript("focusRegion('$code');", null)
                }
            }
        }

        val webSet = webMap.settings
        webSet.javaScriptEnabled = true      // Folium 지도는 자바스크립트(Leaflet)로 그려지므로 꼭 켜야 함
        webSet.builtInZoomControls = true    // 두 손가락 확대/축소
        webSet.displayZoomControls = false   // 화면에 +/- 버튼은 숨김 (지도에 자체 버튼이 있음)

        // 앱 안의 assets 폴더에 있는 파일은 file:///android_asset/ 주소로 읽는다.
        // map.html은 analysis/04_make_map.py를 실행하면 자동으로 이 폴더에 복사된다.
        //  - 전국: 시군구 위험등급 / 서울을 확대하면: 동 단위 위험등급
        //  - 지도 파일은 앱 안에 있지만, 배경 지도(OpenStreetMap)와 지도 프로그램(Leaflet)은
        //    인터넷에서 받아 오므로 인터넷이 연결되어 있어야 보인다 (Manifest의 INTERNET 권한)
        webMap.loadUrl("file:///android_asset/map.html")

        btnMapBack.setOnClickListener {
            finish() // 현재 화면을 닫으면 이전 화면(메인)이 다시 보인다
        }
    }//onCreate()
}//MapActivity

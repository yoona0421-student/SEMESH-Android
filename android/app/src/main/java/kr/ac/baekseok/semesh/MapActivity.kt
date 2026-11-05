package kr.ac.baekseok.semesh

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import androidx.appcompat.app.AppCompatActivity

// 지도 화면: 시군구 위험등급 지도(map.html)를 WebView로 보여준다.
class MapActivity : AppCompatActivity() {

    private lateinit var webMap: WebView
    private lateinit var btnMapBack: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_map)
        title = getString(R.string.title_map)

        webMap = findViewById(R.id.webMap)
        btnMapBack = findViewById(R.id.btnMapBack)

        // WebViewClient를 지정하지 않으면 링크를 눌렀을 때 외부 브라우저가 열린다 (수업 WebView 예제와 같음)
        webMap.webViewClient = WebViewClient()

        val webSet = webMap.settings
        webSet.javaScriptEnabled = true      // Folium 지도는 자바스크립트(Leaflet)로 그려지므로 꼭 켜야 함
        webSet.builtInZoomControls = true    // 두 손가락 확대/축소
        webSet.displayZoomControls = false   // 화면에 +/- 버튼은 숨김 (지도에 자체 버튼이 있음)

        // 앱 안의 assets 폴더에 있는 파일은 file:///android_asset/ 주소로 읽는다.
        // TODO(2주차): analysis/output/map.html이 완성되면 app/src/main/assets/map.html을 그 파일로 교체
        webMap.loadUrl("file:///android_asset/map.html")

        btnMapBack.setOnClickListener {
            finish() // 현재 화면을 닫으면 이전 화면(메인)이 다시 보인다
        }
    }//onCreate()
}//MapActivity

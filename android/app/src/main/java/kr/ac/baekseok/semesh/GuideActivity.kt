package kr.ac.baekseok.semesh

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity

// 가이드 메뉴 화면: GuideData의 주제마다 버튼을 하나씩 만들고,
// 누르면 GuideDetailActivity로 "몇 번째 주제인지"를 넘겨준다.
class GuideActivity : AppCompatActivity() {

    private lateinit var menuContainer: LinearLayout
    private lateinit var btnGuideBack: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_guide)
        title = getString(R.string.title_guide)

        menuContainer = findViewById(R.id.menuContainer)
        btnGuideBack = findViewById(R.id.btnGuideBack)

        // 주제 수만큼 버튼 만들기
        // XML에 버튼을 7개 적는 대신, 코드에서 Button(this)로 만들어 addView로 붙인다.
        for (i in GuideData.topics.indices) {
            val btn = Button(this)
            btn.text = GuideData.topics[i].title
            btn.textSize = 18f
            btn.setOnClickListener {
                val intent = Intent(applicationContext, GuideDetailActivity::class.java)
                // putExtra: 다음 화면에 값을 같이 보낸다 ("topic"이라는 이름표로 번호 i를 보냄)
                intent.putExtra("topic", i)
                startActivity(intent)
            }
            menuContainer.addView(btn)
        }

        btnGuideBack.setOnClickListener {
            finish()
        }
    }//onCreate()
}//GuideActivity

package kr.ac.baekseok.semesh

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

// 지역 위험등급 데이터를 담은 SQLite DB (수업의 myDBHelper와 같은 구조)
//
// [테이블 3개]
//   regionTBL    : 전국 시군구 255곳의 위험등급        ← analysis/output/region.csv
//   dongTBL      : 서울 동 그룹 310곳의 피해율·등급     ← analysis/output/seoul_dong.csv
//   dongAliasTBL : 동 이름 → 동 그룹 대응표 515개       ← analysis/output/seoul_dong_alias.csv
//                  (GPS 주소의 '성수동1가'·'화곡8동' 같은 이름을 '성수동'·'화곡동'으로 바꿀 때 사용)
//
// [데이터를 넣는 시점]
//   앱을 설치하고 DB를 처음 열 때 onCreate()가 딱 한 번 실행된다. 이때 assets 폴더의 CSV를 읽어 넣는다.
//   CSV 파일은 analysis/04_make_map.py를 실행하면 assets 폴더에 자동으로 복사된다.
//   분석을 다시 해서 CSV가 바뀌면 DB_VERSION을 1 올린다 → onUpgrade()가 테이블을 지우고 새로 만든다.
// 조회 결과를 담는 상자 (화면에 보여 줄 값만)
data class RegionInfo(
    val code: String, val sido: String, val sigungu: String, val grade: String,
    val rank: Int, val damage: Int, val accident: Double
)

data class DongInfo(
    val dong: String, val grade: String, val seoulRank: Int, val damage: Int,
    val contracts: Int, val ratio: Double, val lowData: Boolean
)

class DBHelper(private val context: Context) :
    SQLiteOpenHelper(context, "semeshDB", null, DB_VERSION) {

    companion object {
        // 2: regionTBL에 빠졌던 열(보증사고율_보정) 추가 → 이미 설치된 앱의 DB도 새로 만들어지도록 올림
        const val DB_VERSION = 2
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            "CREATE TABLE regionTBL (code CHAR(5) PRIMARY KEY, sido TEXT, sigungu TEXT, grade TEXT, " +
                "rank INTEGER, score REAL, damage INTEGER, damageRate REAL, accident REAL, " +
                "accidentRate REAL, accidentRateEB REAL, scoreR INTEGER);"
        )
        db.execSQL(
            "CREATE TABLE dongTBL (code CHAR(5), sigungu TEXT, dong TEXT, admDongs TEXT, grade TEXT, " +
                "seoulRank INTEGER, damage INTEGER, contracts INTEGER, damageRate REAL, ratio REAL, " +
                "lowData INTEGER, PRIMARY KEY (code, dong));"
        )
        db.execSQL("CREATE TABLE dongAliasTBL (code CHAR(5), name TEXT, dong TEXT, PRIMARY KEY (code, name));")

        // 한 줄씩 넣으면 줄마다 저장이 일어나 느리다 → 트랜잭션으로 묶어 한 번에 저장
        db.beginTransaction()
        try {
            insertCsv(db, "region.csv", "regionTBL", 12)
            insertCsv(db, "seoul_dong.csv", "dongTBL", 11)
            insertCsv(db, "seoul_dong_alias.csv", "dongAliasTBL", 3)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS regionTBL")
        db.execSQL("DROP TABLE IF EXISTS dongTBL")
        db.execSQL("DROP TABLE IF EXISTS dongAliasTBL")
        onCreate(db)
    }

    // ── 조회 ──────────────────────────────────────────────

    // 시도 + 시군구 이름 후보로 regionTBL에서 지역 하나 찾기 (후보는 앞에 있는 것부터 시도)
    fun findRegion(sidoList: List<String>, sigunguCandidates: List<String>): RegionInfo? {
        val db = readableDatabase
        for (sigungu in sigunguCandidates) {
            for (sido in sidoList) {
                val c = db.rawQuery(
                    "SELECT code, sido, sigungu, grade, rank, damage, accident FROM regionTBL " +
                        "WHERE sido = ? AND sigungu = ?;", arrayOf(sido, sigungu)
                )
                c.use {
                    if (it.moveToFirst()) {
                        return RegionInfo(
                            it.getString(0), it.getString(1), it.getString(2), it.getString(3),
                            it.getInt(4), it.getInt(5), it.getDouble(6)
                        )
                    }
                }
            }
        }
        return null
    }

    // 서울 동 찾기: 주소의 동 이름 → dongAliasTBL로 동 그룹 이름 → dongTBL에서 등급
    fun findDong(code: String, name: String): DongInfo? {
        val db = readableDatabase
        val c = db.rawQuery(
            "SELECT d.dong, d.grade, d.seoulRank, d.damage, d.contracts, d.ratio, d.lowData " +
                "FROM dongAliasTBL a JOIN dongTBL d ON a.code = d.code AND a.dong = d.dong " +
                "WHERE a.code = ? AND a.name = ?;", arrayOf(code, name)
        )
        c.use {
            if (!it.moveToFirst()) return null
            return DongInfo(
                it.getString(0), it.getString(1), it.getInt(2), it.getInt(3),
                it.getInt(4), it.getDouble(5), it.getInt(6) == 1
            )
        }
    }

    // assets의 CSV를 읽어 테이블에 넣는다. 첫 줄은 열 이름이라 건너뛴다.
    // CSV의 열 순서를 테이블의 열 순서와 똑같이 만들어 두었기 때문에 그대로 넣으면 된다.
    // 열 개수가 다르면 값이 한 칸씩 밀려 들어가므로(실제로 한 번 겪음) 개수가 다르면 바로 오류를 낸다.
    // (우리 CSV에는 값 안에 쉼표가 없어서 split(",")로 충분하다)
    private fun insertCsv(db: SQLiteDatabase, fileName: String, table: String, columnCount: Int) {
        val marks = List(columnCount) { "?" }.joinToString(",")      // "?,?,?,..."
        val stmt = db.compileStatement("INSERT INTO $table VALUES ($marks);")
        context.assets.open(fileName).bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines.drop(1).forEach { line ->
                val values = line.split(",")
                check(values.size == columnCount) { "$fileName 열 개수 ${values.size}개 ≠ $table ${columnCount}개" }
                stmt.clearBindings()
                for (i in 0 until columnCount) {
                    // 자료부족 열의 True/False는 SQLite에 숫자 1/0으로 저장
                    val v = when (values[i]) { "True" -> "1"; "False" -> "0"; else -> values[i] }
                    stmt.bindString(i + 1, v)
                }
                stmt.executeInsert()
            }
        }
    }
}

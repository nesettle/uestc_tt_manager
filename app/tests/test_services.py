from app.services.common import detect_export_columns, normalize_college, normalize_name, normalize_qq, primary_key
from app.services.jinshuju import extract_forms_from_home_html, normalize_form_title


def test_normalize_name_removes_suffix_note():
    assert normalize_name("王毓远（领队）") == "王毓远"


def test_normalize_college_normalizes_parentheses():
    assert normalize_college("信息与通信工程学院（ 清水河 ）") == "信息与通信工程学院( 清水河 )"


def test_normalize_qq_extracts_digits():
    assert normalize_qq("QQ: 123456") == "123456"


def test_primary_key_prefers_qq():
    assert primary_key("123", "张三", "计算机学院") == ("qq", "123")


def test_normalize_form_title_strips_new_prefix():
    assert normalize_form_title("[新]成电杯正赛单打项目报名") == "成电杯正赛单打项目报名"


def test_extract_forms_from_home_html_reads_entries_links():
    html = """
    <div class="sortable-item-wrap" role="Form" data-handler-id="T0">
      <div>
        <a href="/forms/AbCd12/entries" data-turbolinks="false">
          <div class="thumbnail-view-layout">
            <div class="Form_block__ImqHo">
              <div class="Form_content__JsHUq">
                <div class="Form_scenes__lRj0X"><p class="Form_scene__j4Rzy">报名</p></div>
                <div><span class="">成电杯正赛单打项目报名</span></div>
              </div>
            </div>
          </div>
        </a>
      </div>
    </div>
    """
    forms = extract_forms_from_home_html(html)
    assert forms == [
        {
            "title": "成电杯正赛单打项目报名",
            "url": "https://jinshuju.net/forms/AbCd12/entries",
            "entries_url": "https://jinshuju.net/forms/AbCd12/entries",
            "updated_at": "",
        }
    ]


def test_detect_export_columns_accepts_qualification_college_header():
    headers = [
        "序号",
        "学院部门（教学科研单位、研究机构）",
        "姓名",
        "QQ号",
        "提交时间",
        "修改时间",
    ]
    found = detect_export_columns(headers)
    assert found["college"] == 1
    assert found["name"] == 2
    assert found["qq"] == 3

from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'

def test_empty_submission_and_sample_selection():
 app=AppTest.from_file(str(APP)).run()
 assert not app.exception
 app.button[0].click().run()
 assert 'Enter report text' in app.error[0].value
 app.selectbox[0].select('02_low').run()
 assert 'Hemoglobin | 10.2' in app.text_area[0].value
 assert not app.exception

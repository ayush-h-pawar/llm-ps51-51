import io
import json
from unittest.mock import Mock, patch
import pytest
from pypdf import PdfWriter
from core import ReportError, analyse, flag, parse_json, read_report, validate_input, validate_rows
from llm import LLMClient

@pytest.mark.parametrize('value,reference,expected', [
 ('14.2','12.0-16.0','Within range'), ('10.2','12-16','Low'),
 ('118','70-99','High'), ('12','12-16','Within range'),
 ('16','12-16','Within range'), ('200','<200','High'),
 ('200','<=200','Within range'), ('5','>5','Low'),
 ('5','≥5','Within range'), ('0.3','0.2–0.4','Within range'),
 ('4,500','4,000-11,000','Within range'), ('-1','-2-2','Within range'),
 ('22','','Not assessed'), ('Negative','Negative','Not assessed'),
 ('<5','0-5','Not assessed'), ('5','10-1','Not assessed'),
 ('5','male 4-8; female 3-7','Not assessed'),
 ('4,5','4-6','Not assessed'), ('NaN','0-5','Not assessed'),
 ('1e4','0-20000','Not assessed'), ('5','0-10 mg/dL','Not assessed')])
def test_range_semantics(value, reference, expected):
 assert flag(value,reference)[0] == expected

ROW = {'test':'Hemoglobin','value':'10.2','unit':'g/dL','reference_range':'12.0-16.0','source':'Hemoglobin | 10.2 | g/dL | 12.0-16.0'}

def test_reject_invented_source():
 with pytest.raises(ReportError, match='traced'):
  validate_rows({'tests':[ROW]},'Hemoglobin | 14.0 | g/dL | 12.0-16.0')

def test_reject_invented_range():
 row = {**ROW, 'reference_range':'13-17'}
 with pytest.raises(ReportError, match='traced'):
  validate_rows({'tests':[row]},ROW['source'])

def test_duplicate_rows_removed():
 assert len(validate_rows({'tests':[ROW,ROW]},ROW['source'])) == 1

@pytest.mark.parametrize('text', ['', 'a'*14001])
def test_input_limits(text):
 with pytest.raises(ReportError): validate_input(text)

@pytest.mark.parametrize('text', ['not JSON','[]','{"tests": NaN} trailing'])
def test_bad_json(text):
 with pytest.raises(ReportError): parse_json(text)

def test_fenced_json():
 assert parse_json('```json\n{"tests":[]}\n```') == {'tests':[]}

def test_scanned_pdf_actionable_error():
 writer = PdfWriter(); writer.add_blank_page(width=200,height=200)
 b=io.BytesIO(); writer.write(b)
 with pytest.raises(ReportError, match='OCR'): read_report('scan.pdf',b.getvalue())

def test_bad_file_and_bad_encoding():
 with pytest.raises(ReportError): read_report('bad.pdf',b'invalid pdf')
 with pytest.raises(ReportError): read_report('bad.txt',b'\xff')
 with pytest.raises(ReportError): read_report('bad.exe',b'123')
 with pytest.raises(ReportError): read_report('big.txt',b'x'*(5*1024*1024+1))

def test_no_tests():
 with pytest.raises(ReportError,match='No laboratory'): validate_rows({'tests':[]},'hello')

def test_pipeline_real_contract_with_mocked_transport():
 client=Mock(model='test',provider='test')
 client.complete.side_effect=[json.dumps({'tests':[ROW]}),json.dumps({'explanations':[{'id':0,'explanation':'Hemoglobin carries oxygen. The value is below the printed range.'}]})]
 result=analyse(ROW['source'],client)
 assert result['tests'][0]['status']=='Low'
 assert result['warnings']==[]
 assert json.loads(client.complete.call_args.args[1]) == [{'id':0,'test':'Hemoglobin'}]

def test_bad_explanation_preserves_calculated_flags():
 client=Mock(model='test',provider='test')
 client.complete.side_effect=[json.dumps({'tests':[ROW]}),'invalid']
 result=analyse(ROW['source'],client)
 assert result['tests'][0]['status']=='Low'
 assert result['warnings']

@pytest.mark.parametrize('provider', ['Ollama','Groq','llama.cpp'])
def test_provider_protocol(provider):
 response=Mock()
 response.json.return_value={'message':{'content':'{}'},'choices':[{'message':{'content':'{}'}}]}
 with patch('llm.requests.post',return_value=response) as post:
  assert LLMClient(provider,'test','dummy-key').complete('system','user')=='{}'
  body=post.call_args.kwargs['json']
  assert body['messages'][0]['role']=='system'
  assert body['messages'][1]['content']=='user'

def test_missing_key():
 with pytest.raises(ReportError,match='API key'): LLMClient('Groq','model')

def test_reject_numeric_substring():
 row={'test':'Glucose','value':'1','unit':'mg/dL','reference_range':'70-99'}
 with pytest.raises(ReportError,match='traced'):
  validate_rows({'tests':[row]},'Glucose | 118 | mg/dL | 70-99')

def test_source_located_without_model_copy():
 row={k:v for k,v in ROW.items() if k!='source'}
 assert validate_rows({'tests':[row]},ROW['source'])[0]['source']==ROW['source']

def test_name_capitalisation_restored_from_source():
 row={**ROW,'test':'hemoglobin'}
 assert validate_rows({'tests':[row]},ROW['source'])[0]['test']=='Hemoglobin'

def test_detect_omitted_delimited_row():
 report='Test | Result | Unit | Reference range\n'+ROW['source']+'\nCRP | Negative | | Negative'
 with pytest.raises(ReportError,match='omitted'):
  validate_rows({'tests':[ROW]},report)

def test_delimited_source_columns_take_precedence():
 row={'test':'Total cholesterol','value':'225','unit':'<200','reference_range':''}
 report='Test | Result | Unit | Reference range\nTotal cholesterol | 225 | mg/dL | <200'
 result=validate_rows({'tests':[row]},report)[0]
 assert result['unit']=='mg/dL'
 assert result['reference_range']=='<200'
 assert result['status']=='High'
 assert result['validation_notes']

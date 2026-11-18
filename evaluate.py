"""Run the five synthetic inputs through a real configured model."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from core import analyse
from llm import LLMClient

EXPECTED = {
 '01_normal': ['Within range', 'Within range', 'Within range'],
 '02_low': ['Low', 'Low'],
 '03_high': ['High', 'High'],
 '04_missing_range': ['Not assessed', 'Not assessed'],
 '05_boundaries': ['Within range', 'High', 'Not assessed'],
}

class RecordingClient(LLMClient):
 def complete(self, system, user):
  response=super().complete(system,user)
  self.calls.append({'system':system,'user':user,'response':response})
  return response

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--provider',default='llama.cpp',choices=['llama.cpp','Ollama','Groq'])
 parser.add_argument('--model',default='qwen2.5-1.5b')
 parser.add_argument('--base-url',default='http://127.0.0.1:8080')
 args=parser.parse_args()
 import os
 client=RecordingClient(args.provider,args.model,os.getenv('GROQ_API_KEY',''),args.base_url)
 root=Path(__file__).parent
 (root/'evidence').mkdir(exist_ok=True)
 summary=[]
 for sample in sorted((root/'samples').glob('*.txt')):
  start=time.monotonic()
  client.calls=[]
  try:
   result=analyse(sample.read_text(),client)
  finally:
   (root/'evidence'/f'{sample.stem}_calls.json').write_text(json.dumps(client.calls,indent=2,ensure_ascii=False))
  actual=[r['status'] for r in result['tests']]
  record={'sample':sample.name,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'seconds':round(time.monotonic()-start,2),'expected':EXPECTED[sample.stem],'actual':actual,'passed':actual==EXPECTED[sample.stem] and not result['warnings'],'result':result}
  (root/'evidence'/f'{sample.stem}.json').write_text(json.dumps(record,indent=2,ensure_ascii=False))
  summary.append({k:v for k,v in record.items() if k!='result'})
  print(json.dumps(summary[-1]),flush=True)
 (root/'evidence'/'summary.json').write_text(json.dumps(summary,indent=2))
 if not all(r['passed'] for r in summary): raise SystemExit('One or more model checks failed; inspect evidence.')

if __name__=='__main__': main()

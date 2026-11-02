import json, os, re, html
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

load_dotenv()
app = FastAPI(title="LinkedIn SEO AI API", version="1.0.0")
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGIN","http://localhost:5173").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB","15")) * 1024 * 1024
ALLOWED = {"application/pdf","image/png","image/jpeg","image/webp"}

@app.get("/")
def root():
    return {"service":"LinkedIn SEO AI API","status":"ok"}

@app.get("/api/health")
def health():
    return {"status":"ok","gemini_configured":bool(os.getenv("GEMINI_API_KEY")),
            "resend_configured":bool(os.getenv("RESEND_API_KEY"))}

def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try: return json.loads(text)
    except json.JSONDecodeError:
        a,b=text.find("{"),text.rfind("}")
        if a>=0 and b>a: return json.loads(text[a:b+1])
        raise

def prompt(data):
    return """You are a rigorous LinkedIn profile strategist. Analyze supplied profile data and attached PDF/screenshots. Be specific and direct. Never invent employers, qualifications, skills, metrics or achievements. Treat missing facts as gaps. Optimize for the target role.

PROFILE DATA:
""" + json.dumps(data,ensure_ascii=False,indent=2) + """

Return ONLY valid JSON with these keys:
{
 "overall_score": 0,
 "score_explanation": "short reason",
 "executive_summary": "summary",
 "priority_fixes": ["..."],
 "headline_options": ["exactly 3 options"],
 "about_options": ["exactly 2 complete About drafts"],
 "experience_improvements": [{"role":"...","current_issue":"...","recommended_version":"...","missing_evidence":"..."}],
 "skills_analysis": {"keep":["..."],"add":["..."],"remove_or_deprioritize":["..."],"reasoning":"..."},
 "education_and_projects": ["..."],
 "visual_analysis": {"profile_photo":"...","banner":"...","other_visuals":"..."},
 "custom_posts": [{"topic":"...","post_text":"...","purpose":"..."}],
 "networking_plan": {"people_to_connect_with":["..."],"connection_note":"...","avoid":["..."]},
 "weekly_action_plan": [{"day_or_period":"...","actions":["..."]}],
 "missing_information": ["..."],
 "disclaimer": "Verify all claims before publishing."
}
Provide 3 headlines, 2 About drafts and 3-5 custom posts. Make advice specific to target role/job description. If screenshots were not provided, say visual assessment was not possible. Score 0-100. Avoid generic filler.
"""

def send_report(to_email,name,report):
    key, sender = os.getenv("RESEND_API_KEY"), os.getenv("RESEND_FROM")
    if not key or not sender:
        return False,"Email not sent: configure RESEND_API_KEY and RESEND_FROM in backend/.env."
    esc=lambda x: html.escape(str(x or ""))
    blocks=[f"<h2>Profile score: {esc(report.get('overall_score'))}/100</h2>",
            f"<p>{esc(report.get('score_explanation'))}</p>",
            f"<h3>Executive summary</h3><p>{esc(report.get('executive_summary'))}</p>"]
    for title,keyname in [("Priority fixes","priority_fixes"),("Headline options","headline_options"),
                          ("About options","about_options"),("Missing information","missing_information")]:
        items=report.get(keyname,[])
        if items: blocks.append(f"<h3>{title}</h3><ul>"+ "".join(f"<li>{esc(v)}</li>" for v in items)+"</ul>")
    for post in report.get("custom_posts",[]):
        blocks.append(f"<h3>{esc(post.get('topic'))}</h3><p>{esc(post.get('post_text')).replace(chr(10),'<br>')}</p>")
    blocks.append(f"<p><i>{esc(report.get('disclaimer'))}</i></p>")
    payload={"from":sender,"to":[to_email],"subject":"Your LinkedIn SEO profile analysis",
             "html":f"<div style='font-family:Arial;max-width:760px;margin:auto;line-height:1.6'><h1>Your LinkedIn SEO report</h1><p>Hello {esc(name)},</p>{''.join(blocks)}</div>"}
    try:
        r=requests.post("https://api.resend.com/emails",
          headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=30)
        if r.status_code>=400:
            try: detail=r.json().get("message",r.text)
            except Exception: detail=r.text
            return False,f"Resend rejected email ({r.status_code}): {detail}"
        return True,"Report emailed successfully."
    except requests.RequestException as e: return False,f"Email delivery failed: {e}"

@app.post("/api/analyze")
async def analyze(
 name:str=Form(...), email:str=Form(...), current_role:str=Form(""), target_role:str=Form(...),
 target_industry:str=Form(""), target_company:str=Form(""), career_objective:str=Form(""),
 headline:str=Form(""), about:str=Form(""), experience:str=Form(""), skills:str=Form(""),
 education:str=Form(""), certifications:str=Form(""), projects:str=Form(""),
 existing_posts:str=Form(""), target_job_description:str=Form(""),
 files:list[UploadFile]|None=File(default=None)):
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(500,"GEMINI_API_KEY is not configured on the backend.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422,"Enter a valid email address.")
    data={k:v for k,v in locals().copy().items() if k in {
      "name","email","current_role","target_role","target_industry","target_company","career_objective",
      "headline","about","experience","skills","education","certifications","projects","existing_posts","target_job_description"}}
    contents=[prompt(data)]; names=[]
    for f in files or []:
        if not f.filename: continue
        raw=await f.read(); mime=f.content_type or ""
        if len(raw)>MAX_BYTES: raise HTTPException(413,f"{f.filename} exceeds the upload limit.")
        if mime not in ALLOWED: raise HTTPException(415,f"Unsupported file type {mime}; use PDF, PNG, JPG or WEBP.")
        contents.append(types.Part.from_bytes(data=raw,mime_type=mime)); names.append(f.filename)
    try:
        client=genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),
          contents=contents,config=types.GenerateContentConfig(response_mime_type="application/json",temperature=0.35))
        report=parse_json(response.text)
    except Exception as e: raise HTTPException(502,f"Gemini analysis failed: {e}")
    sent,message=send_report(email,name,report)
    return {"success":True,"report":report,"email_sent":sent,"email_message":message,"files_processed":names}

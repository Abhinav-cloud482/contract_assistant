import re
import docx
import PyPDF2
import spacy
import streamlit as st

@st.cache_resource
def load_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        return None

nlp = load_nlp()

def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    return "\n".join(text)

def get_contract_text(uploaded_file):
    if uploaded_file.name.endswith('.pdf'):
        return extract_text_from_pdf(uploaded_file)
    elif uploaded_file.name.endswith('.docx'):
        return extract_text_from_docx(uploaded_file)
    elif uploaded_file.name.endswith('.txt'):
        return str(uploaded_file.read(), "utf-8")
    return ""

def analyze_contract(text):
    results = {
        "entities": {"Organizations": set(), "Dates": set(), "Money": set()},
        "risks": [],
        "clauses": {"Termination": [], "Indemnification": [], "Governing Law": []}
    }
    
    if nlp:
        doc = nlp(text[:50000]) # Cap text size for performance
        for ent in doc.ents:
            if ent.label_ == "ORG" and len(ent.text.strip()) > 2:
                results["entities"]["Organizations"].add(ent.text.strip())
            elif ent.label_ == "DATE":
                results["entities"]["Dates"].add(ent.text.strip())
            elif ent.label_ == "MONEY":
                results["entities"]["Money"].add(ent.text.strip())

    for key in results["entities"]:
        results["entities"][key] = sorted(list(results["entities"][key]))[:10]

    risk_patterns = {
        "Automatic Renewal / Auto-renew": r"(automatically renews|auto-renew|automatic extension)",
        "Strict Liability / Uncapped Liability": r"(unlimited liability|strict liability|sole liability)",
        "Hidden / Extra Fees": r"(additional charges|late fees|penalty fee|extra charges)",
        "Governing Law Outside Jurisdiction": r"(governed by the laws of|jurisdiction of the courts of)"
    }
    
    clause_patterns = {
        "Termination": r"([^.\n]*terminate[^.\n]*\.)",
        "Indemnification": r"([^.\n]*indemnify[^.\n]*\.)",
        "Governing Law": r"([^.\n]*governing law[^.\n]*\.)"
    }

    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        sentence_clean = sentence.strip()
        if not sentence_clean:
            continue
            
        for risk_name, pattern in risk_patterns.items():
            if re.search(pattern, sentence_clean, re.IGNORECASE):
                results["risks"].append({"type": risk_name, "context": sentence_clean})
        
        for clause_name, pattern in clause_patterns.items():
            if re.search(pattern, sentence_clean, re.IGNORECASE):
                if len(results["clauses"][clause_name]) < 3:
                    results["clauses"][clause_name].append(sentence_clean)

    return results

st.set_page_config(page_title="Contract Analysis Assistant", page_icon="document", layout="wide")

st.title("Contract Analysis Assistant")
st.markdown("Upload a legal contract (**PDF, DOCX, or TXT**) to automatically extract key entities, flag potential risks, and isolate important clauses.")

st.sidebar.header("Upload Document")
uploaded_file = st.sidebar.file_uploader("Choose a contract file", type=["pdf", "docx", "txt"])

if uploaded_file:
    with st.spinner("Extracting text and analyzing contract..."):
        contract_text = get_contract_text(uploaded_file)
        
        if contract_text.strip() == "":
            st.error("Could not extract text from the document. Please ensure it is not scanned/an image.")
        else:
            analysis = analyze_contract(contract_text)
            
            tab1, tab2, tab3, tab4 = st.tabs(["Executive Summary", "Risk Assessment", "Key Clauses", "Raw Text"])
            
            with tab1:
                st.subheader("Key Entities Found")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("**Organizations / Parties**")
                    if analysis["entities"]["Organizations"]:
                        for org in analysis["entities"]["Organizations"]:
                            st.write(f"- {org}")
                    else:
                        st.info("No clear organizations detected.")
                        
                with col2:
                    st.markdown("**Important Dates**")
                    if analysis["entities"]["Dates"]:
                        for date in analysis["entities"]["Dates"]:
                            st.write(f"- {date}")
                    else:
                        st.info("No dates detected.")
                        
                with col3:
                    st.markdown("**Financial Values Mentioned**")
                    if analysis["entities"]["Money"]:
                        for money in analysis["entities"]["Money"]:
                            st.write(f"- {money}")
                    else:
                        st.info("No monetary amounts detected.")

            with tab2:
                st.subheader("Potential Risks Flags")
                if analysis["risks"]:
                    for risk in analysis["risks"]:
                        with st.expander(f"Flagged: {risk['type']}"):
                            st.warning(f"**Context:** ... {risk['context']} ...")
                else:
                    st.success("No standard high-risk keywords found in the text.")

            with tab3:
                st.subheader("Isolated Key Clauses")
                for clause_type, lines in analysis["clauses"].items():
                    st.markdown(f"### {clause_type} Clauses")
                    if lines:
                        for line in lines:
                            st.info(f"\"{line}\"")
                    else:
                        st.write("*No explicit matches found.*")

            with tab4:
                st.subheader("Extracted Document Content")
                st.text_area("Full Text View", contract_text, height=400)
else:
    st.info("Please upload a document in the sidebar to begin the analysis.")

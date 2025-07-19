# dar_processor.py
import pdfplumber
import google.generativeai as genai
import json
import requests
import streamlit as st
from typing import List, Dict, Any
from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema # Using your models.py

def preprocess_pdf_text(pdf_path_or_bytes) -> str:
    """
    Extracts all text from all pages of the PDF using pdfplumber,
    attempting to preserve layout for better LLM understanding.
    """
    processed_text_parts = []
    try:
        with pdfplumber.open(pdf_path_or_bytes) as pdf:
            for i, page in enumerate(pdf.pages):
                # Using layout=True helps preserve reading order for the LLM.
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)

                if page_text is None:
                    page_text = f"[INFO: Page {i + 1} yielded no text directly]"
                else:
                    # Basic sanitization
                    page_text = page_text.replace("None", "")

                processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")

        full_text = "".join(processed_text_parts)
        return full_text
    except Exception as e:
        error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
        print(error_msg)
        return error_msg

def get_structured_data_with_gemini(api_key: str, text_content: str) -> ParsedDARReport:
    """
    Calls the Gemini API with the PDF text and parses the response.
    This version keeps all monetary values in Rupees as requested.
    """
    if text_content.startswith("Error processing PDF"):
        return ParsedDARReport(parsing_errors=text_content)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    # --- MODIFIED PROMPT ---
    # Instructions now explicitly state to keep all values in Rupees.
    prompt = f"""
    You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
    extract the specified information and structure it as a JSON object.

    The JSON object should follow this structure precisely:
    {{
      "header": {{
        "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
        "gstin": "string or null",
        "trade_name": "string or null",
        "category": "string ('Large', 'Medium', 'Small') or null",
        "total_amount_detected_overall_rs": "float or null (in Rupees)",
        "total_amount_recovered_overall_rs": "float or null (in Rupees)"
      }},
      "audit_paras": [
        {{
          "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
          "audit_para_heading": "string or null (title of the para)",
          "revenue_involved_lakhs_rs": "float or null (Value MUST be in RUPEES)",
          "revenue_recovered_lakhs_rs": "float or null (Value MUST be in RUPEES)",
          "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
        }}
      ],
      "parsing_errors": "string or null"
    }}

    Key Instructions:
    1.  Header Info: Find `audit_group_number`, `gstin`, `trade_name`, `category`, and overall totals. These totals should be in Rupees.
    2.  Audit Paras: Identify each para. Extract `audit_para_number`, `audit_para_heading`, and `status_of_para`.
    3.  **CRITICAL**: For `revenue_involved_lakhs_rs` and `revenue_recovered_lakhs_rs`, extract the monetary value directly in **Rupees**. DO NOT convert the amount to Lakhs, even though 'lakhs' is in the field name. The value must be a float.
    4.  If a value is not found, use null. All monetary values must be numbers (float).
    5.  The 'audit_paras' list should contain one object per para. If none are found, provide an empty list [].

    DAR Text Content:
    --- START OF DAR TEXT ---
    {text_content}
    --- END OF DAR TEXT ---

    Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
    """

    try:
        response = model.generate_content(prompt)

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:-3].strip()
        elif cleaned_response_text.startswith("```"):
             cleaned_response_text = cleaned_response_text[3:-3].strip()


        if not cleaned_response_text:
            return ParsedDARReport(parsing_errors="Gemini returned an empty response.")

        # Parse and validate the JSON data using Pydantic models
        json_data = json.loads(cleaned_response_text)
        return ParsedDARReport(**json_data)

    except json.JSONDecodeError as e:
        raw_response = "Response object not available"
        if 'response' in locals() and hasattr(response, 'text'):
            raw_response = response.text
        return ParsedDARReport(parsing_errors=f"Gemini output was not valid JSON: {e}. Raw response: {raw_response[:500]}...")
    except Exception as e:
        return ParsedDARReport(parsing_errors=f"An unexpected error occurred during Gemini processing: {e}")


def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
    """
    Calls the OpenRouter API with the PDF text and parses the response.
    This version keeps all monetary values in Rupees as requested.
    """
    if text_content.startswith("Error processing PDF"):
        return ParsedDARReport(parsing_errors=text_content)

    openrouter_api_key = st.secrets.get("openrouter_api_key", "")
    if not openrouter_api_key:
        error_msg = "OpenRouter API key not found in Streamlit secrets."
        return ParsedDARReport(parsing_errors=error_msg)

    # --- MODIFIED PROMPT ---
    # Instructions now explicitly state to keep all values in Rupees.
    prompt = f"""
    You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
    extract the specified information and structure it as a JSON object.

    The JSON object should follow this structure precisely:
    {{
      "header": {{
        "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
        "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
        "total_amount_detected_overall_rs": "float or null (in Rupees)",
        "total_amount_recovered_overall_rs": "float or null (in Rupees)"
      }},
      "audit_paras": [
        {{
          "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
          "audit_para_heading": "string or null (title of the para)",
          "revenue_involved_lakhs_rs": "float or null (Value MUST be in RUPEES)",
          "revenue_recovered_lakhs_rs": "float or null (Value MUST be in RUPEES)",
          "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
        }}
      ],
      "parsing_errors": "string or null"
    }}

    Key Instructions:
    1.  Header Info: Find `audit_group_number`, `gstin`, `trade_name`, `category`, and overall totals in Rupees.
    2.  Audit Paras: Identify each para. Extract `audit_para_number`, `audit_para_heading`, and `status_of_para`.
    3.  **CRITICAL**: For `revenue_involved_lakhs_rs` and `revenue_recovered_lakhs_rs`, extract the monetary value directly in **Rupees**. DO NOT convert the amount to Lakhs, even though 'lakhs' is in the field name. The value must be a float.
    4.  If a value is not found, use null. All monetary values must be numbers (float).
    5.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].

    DAR Text Content:
    --- START OF DAR TEXT ---
    {text_content}
    --- END OF DAR TEXT ---

    Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
    """

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
            },
            data=json.dumps({
                "model": "deepseek/deepseek-r1:free",
                "messages": [{"role": "user", "content": prompt}]
            })
        )

        if response.status_code != 200:
            error_message = f"API Error from OpenRouter: {response.status_code} - {response.text}"
            return ParsedDARReport(parsing_errors=error_message)

        response_data = response.json()
        content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Clean up markdown code block if present
        if content_str.strip().startswith("```json"):
            content_str = content_str.strip()[7:-3].strip()
        elif content_str.strip().startswith("```"):
             content_str = content_str.strip()[3:-3].strip()

        if not content_str:
            return ParsedDARReport(parsing_errors="LLM returned an empty response.")

        # Parse and validate the JSON data using Pydantic models
        json_data = json.loads(content_str)
        return ParsedDARReport(**json_data)

    except requests.exceptions.RequestException as e:
        return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
    except json.JSONDecodeError as e:
        return ParsedDARReport(parsing_errors=f"LLM output was not valid JSON: {e}. Raw response: {content_str[:500]}...")
    except Exception as e:
        return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")# # dar_processor.py

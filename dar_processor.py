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
# import pdfplumber
# import google.generativeai as genai
# import json
# from typing import List, Dict, Any
# from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema  # Using your models.py
# import requests
# import streamlit as st
# def preprocess_pdf_text(pdf_path_or_bytes) -> str:
#     """
#     Extracts all text from all pages of the PDF using pdfplumber,
#     attempting to preserve layout for better LLM understanding.
#     """
#     processed_text_parts = []
#     try:
#         with pdfplumber.open(pdf_path_or_bytes) as pdf:
#             for i, page in enumerate(pdf.pages):
#                 # Using layout=True can help preserve the reading order and structure
#                 # which might be beneficial for the LLM.
#                 page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)

#                 if page_text is None:
#                     page_text = f"[INFO: Page {i + 1} yielded no text directly]"
#                 else:
#                     # Basic sanitization: replace "None" strings that might have been literally extracted
#                     page_text = page_text.replace("None", "")

#                 processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")

#         full_text = "".join(processed_text_parts)
#         # print(f"Full preprocessed text length: {len(full_text)}") # For debugging
#         # print(full_text[:2000]) # Print snippet for debugging
#         return full_text
#     except Exception as e:
#         error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
#         print(error_msg)
#         return error_msg

# def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
#     """
#     Calls the OpenRouter API with the PDF text and parses the response.
#     """
#     if text_content.startswith("Error processing PDF"):
#         return ParsedDARReport(parsing_errors=text_content)

#     # --- NEW: OpenRouter Configuration ---
#     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
#     if not openrouter_api_key:
#         error_msg = "OpenRouter API key not found in Streamlit secrets."
#         return ParsedDARReport(parsing_errors=error_msg)

#     # The detailed prompt remains the same to guide the new model
#     prompt = f"""
#     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
#     extract the specified information and structure it as a JSON object.

#     The JSON object should follow this structure precisely:
#     {{
#       "header": {{
#         "audit_group_number": "integer or null (e.g., if 'Group-VI' becomes 6; must be 1-30)",
#         "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
#         "total_amount_detected_overall_rs": "float or null (in Rupees)",
#         "total_amount_recovered_overall_rs": "float or null (in Rupees)"
#       }},
#       "audit_paras": [
#         {{
#           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1; must be 1-50)",
#           "audit_para_heading": "string or null (title of the para)",
#           "revenue_involved_lakhs_rs": "float or null (in Lakhs of Rupees, e.g., 50000 becomes 0.5)",
#           "revenue_recovered_lakhs_rs": "float or null (in Lakhs of Rupees)",
#           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
#         }}
#       ],
#       "parsing_errors": "string or null"
#     }}

#     Key Instructions:
#     1.  Header Info: Find `audit_group_number`, `gstin`, `trade_name`, `category`, and overall totals in Rupees.
#     2.  Audit Paras: Identify each para. Extract `audit_para_number`, `audit_para_heading`, and `status_of_para`.
#     3.  Convert revenue figures for individual paras to LAKHS of Rupees.
#     4.  If a value is not found, use null. All monetary values must be numbers (float).
#     5.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].

#     DAR Text Content:
#     --- START OF DAR TEXT ---
#     {text_content}
#     --- END OF DAR TEXT ---

#     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
#     """

#     try:
#         response = requests.post(
#             url="https://openrouter.ai/api/v1/chat/completions",
#             headers={
#                 "Authorization": f"Bearer {openrouter_api_key}",
#             },
#             data=json.dumps({
#                 #"model": "deepseek/deepseek-r1-0528-qwen3-8b:free", # A powerful free model
#                 "model":  "deepseek/deepseek-r1:free",
#                 "messages": [{"role": "user", "content": prompt}]
#             })
#         )

#         if response.status_code != 200:
#             error_message = f"API Error from OpenRouter: {response.status_code} - {response.text}"
#             return ParsedDARReport(parsing_errors=error_message)

#         response_data = response.json()
#         # Correctly access the content from the response structure
#         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
#         print(content_str)
#         # Clean up markdown code block if present
#         if content_str.strip().startswith("```json"):
#             content_str = content_str.strip()[7:-3]

#         if not content_str:
#             return ParsedDARReport(parsing_errors="LLM returned an empty response.")

#         # Parse and validate the JSON data using Pydantic models
#         json_data = json.loads(content_str)
#         return ParsedDARReport(**json_data)

#     except requests.exceptions.RequestException as e:
#         return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
#     except json.JSONDecodeError as e:
#         return ParsedDARReport(parsing_errors=f"LLM output was not valid JSON: {e}. Raw response: {content_str[:500]}...")
#     except Exception as e:
#         return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")
# def get_structured_data_with_gemini(api_key: str, text_content: str) -> ParsedDARReport:
#     """
#     Calls Gemini API with the full PDF text and parses the response.
#     """
#     if text_content.startswith("Error processing PDF with pdfplumber:"):
#         return ParsedDARReport(parsing_errors=text_content)

#     genai.configure(api_key=api_key)
#     # Using a model capable of handling potentially larger context and complex instructions.
#     # 'gemini-1.5-flash-latest' is a good balance.
#     model = genai.GenerativeModel('gemini-1.5-flash-latest')

#     prompt = f"""
#     You are an expert GST audit report analyst. Based on the following FULL text from a Departmental Audit Report (DAR),
#     where all text from all pages, including tables, is provided, extract the specified information
#     and structure it as a JSON object. Focus on identifying narrative sections for audit para details,
#     even if they are intermingled with tabular data. Notes like "[INFO: ...]" in the text are for context only.

#     The JSON object should follow this structure precisely:
#     {{
#       "header": {{
#         "audit_group_number": "integer or null (e.g., if 'Group-VI' or 'Gr 6', extract 6; must be between 1 and 30)",
#         "gstin": "string or null",
#         "trade_name": "string or null",
#         "category": "string ('Large', 'Medium', 'Small') or null",
#         "total_amount_detected_overall_rs": "float or null (numeric value in Rupees)",
#         "total_amount_recovered_overall_rs": "float or null (numeric value in Rupees)"
#       }},
#       "audit_paras": [
#         {{
#           "audit_para_number": "integer or null (primary number from para heading, e.g., for 'Para-1...' use 1; must be between 1 and 50)",
#           "audit_para_heading": "string or null (the descriptive title of the para)",
#           "revenue_involved_lakhs_rs": "float or null (numeric value in Lakhs of Rupees, e.g., Rs. 50,000 becomes 0.5)",
#           "revenue_recovered_lakhs_rs": "float or null (numeric value in Lakhs of Rupees)",
#           "status_of_para": "string or null (Possible values: 'Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to paid', 'Not agreed')"
#         }}
#       ],
#       "parsing_errors": "string or null (any notes about parsing issues, or if extraction is incomplete)"
#     }}

#     Key Instructions:
#     1.  **Header Information (usually from first 1-3 pages):**
#         - For `audit_group_number`: Extract the group number as an integer. Example: 'Group-VI' or 'Gr 6' becomes 6. Must be between 1 and 30. If not determinable as such, return null.
#         - Extract `gstin`, `trade_name`, and `category`.
#         - `total_amount_detected_overall_rs`: Grand total detection for the entire audit (in Rupees).
#         - `total_amount_recovered_overall_rs`: Grand total recovery for the entire audit (in Rupees).
#     2.  **Audit Paras (can appear on any page after initial header info):**
#         - Identify each distinct audit para. They often start with "Para-X" or similar.
#         - For `audit_para_number`: Extract the main number from the para heading as an integer (e.g., "Para-1..." or "Para 1." becomes 1). Must be an integer between 1 and 50.
#         - Extract `audit_para_heading` (the descriptive title/summary of the para).
#         - Extract "Revenue involved" specific to THAT para and convert it to LAKHS of Rupees (amount_in_rs / 100000.0).
#         - Extract "Revenue recovered" specific to THAT para (e.g. from 'amount paid' or 'party contention') and convert it to LAKHS of Rupees.
#         - Extract `status_of_para`. Strictly choose from: 'Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to paid', 'Not agreed'. If the status is unclear or different, use null.
#     3.  If any field's value is not found or cannot be determined, use null for that field.
#     4.  Ensure all monetary values are numbers (float).
#     5.  The 'audit_paras' list should contain one object per para. If no paras found, provide an empty list [].

#     DAR Text Content:
#     --- START OF DAR TEXT ---
#     {text_content}
#     --- END OF DAR TEXT ---

#     Provide ONLY the JSON object as your response. Do not include any explanatory text before or after the JSON.
#     """

#     print("\n--- Calling Gemini with simplified full text approach ---")
#     # print(f"Prompt (first 500 chars):\n{prompt[:500]}...") # For debugging

#     try:
#         response = model.generate_content(prompt)

#         cleaned_response_text = response.text.strip()
#         if cleaned_response_text.startswith("```json"):
#             cleaned_response_text = cleaned_response_text[7:]
#         elif cleaned_response_text.startswith("`json"):
#             cleaned_response_text = cleaned_response_text[6:]
#         if cleaned_response_text.endswith("```"):
#             cleaned_response_text = cleaned_response_text[:-3]

#         if not cleaned_response_text:
#             error_message = "Gemini returned an empty response."
#             print(error_message)
#             return ParsedDARReport(parsing_errors=error_message)

#         json_data = json.loads(cleaned_response_text)
#         parsed_report = ParsedDARReport(**json_data)  # Validation against your models.py
#         print(f"Gemini call successful. Paras found: {len(parsed_report.audit_paras)}")
#         if parsed_report.audit_paras:
#             for idx, para_obj in enumerate(parsed_report.audit_paras):
#                 if not para_obj.audit_para_heading:
#                     print(
#                         f"  Note: Para {idx + 1} (Number: {para_obj.audit_para_number}) has a missing heading from Gemini.")
#         return parsed_report
#     except json.JSONDecodeError as e:
#         raw_response_text = "No response text available"
#         if 'response' in locals() and hasattr(response, 'text'):
#             raw_response_text = response.text
#         error_message = f"Gemini output was not valid JSON: {e}. Response: '{raw_response_text[:1000]}...'"
#         print(error_message)
#         return ParsedDARReport(parsing_errors=error_message)
#     except Exception as e:
#         raw_response_text = "No response text available"
#         if 'response' in locals() and hasattr(response, 'text'):
#             raw_response_text = response.text
#         error_message = f"Error during Gemini/Pydantic: {type(e).__name__} - {e}. Response: {raw_response_text[:500]}"
#         print(error_message)
#         return ParsedDARReport(parsing_errors=error_message)
#         # # dar_processor.py

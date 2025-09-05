# dar_processor.py
import pdfplumber
import google.generativeai as genai
import json
import requests
import streamlit as st
import time
from typing import List, Dict, Any, Tuple
from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema
from config import BATCH_SYSTEM_PROMPT, TAXPAYER_CLASSIFICATION_OPTIONS

def preprocess_pdf_text(pdf_path_or_bytes) -> str:
    """
    Extracts all text from all pages of the PDF using pdfplumber,
    attempting to preserve layout for better LLM understanding.
    """
    processed_text_parts = []
    try:
        with pdfplumber.open(pdf_path_or_bytes) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)
                if page_text is None:
                    page_text = f"[INFO: Page {i + 1} yielded no text directly]"
                else:
                    page_text = page_text.replace("None", "")
                processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")
        full_text = "".join(processed_text_parts)
        return full_text
    except Exception as e:
        error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
        print(error_msg)
        return error_msg

def try_openrouter_model(model_name: str, prompt: str, openrouter_api_key: str, max_retries: int = 1) -> Tuple[str, str]:
    """
    Try a specific OpenRouter model with retries and exponential backoff.
    Returns (content, error_message). If successful, error_message is None.
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_api_key}"},
                data=json.dumps({
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}]
                }),
                timeout=60  # Add timeout to prevent hanging
            )

            if response.status_code == 200:
                response_data = response.json()
                content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return content_str, None
            elif response.status_code == 429:
                # Rate limit - wait and retry
                wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s
                if attempt < max_retries - 1:
                    print(f"Rate limited on {model_name}, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    return "", f"Rate limited on {model_name}: {response.text}"
            else:
                return "", f"API Error from {model_name}: {response.status_code} - {response.text}"

        except requests.exceptions.Timeout:
            error_msg = f"Timeout error with {model_name}"
            if attempt < max_retries - 1:
                print(f"{error_msg}, retrying...")
                time.sleep(2)
                continue
            return "", error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error with {model_name}: {e}"
            if attempt < max_retries - 1:
                print(f"{error_msg}, retrying...")
                time.sleep(2)
                continue
            return "", error_msg
        except Exception as e:
            return "", f"Unexpected error with {model_name}: {e}"
    
    return "", f"All retries failed for {model_name}"

def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
    """
    Calls multiple LLM APIs with fallback strategy to handle rate limits.
    Tries models in order: DeepSeek R1 -> Qwen3 Coder -> Gemini 2.0 Flash
    """
    if text_content.startswith("Error processing PDF"):
        return ParsedDARReport(parsing_errors=text_content)

    openrouter_api_key = st.secrets.get("openrouter_api_key", "")
    if not openrouter_api_key:
        error_msg = "OpenRouter API key not found in Streamlit secrets."
        return ParsedDARReport(parsing_errors=error_msg)

    prompt = f"""
    You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
    extract the specified information and structure it as a JSON object.

    The JSON object should follow this structure precisely:
    {{
      "header": {{
        "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
        "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
        "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
        "total_amount_detected_overall_rs": "float or null (in Rupees)",
        "total_amount_recovered_overall_rs": "float or null (in Rupees)",
        "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
      }},
      "audit_paras": [
        {{
          "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
          "audit_para_heading": "string or null (title of the para)",
          "revenue_involved_rs": "float or null ( in RUPEES)",
          "revenue_recovered_rs": "float or null ( in RUPEES)",
          "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
        }}
      ],
      "parsing_errors": "string or null"
    }}

    Key Instructions:
    1.  Header Info: Find all header fields.
    2.  Taxpayer Classification: Identify the taxpayer nature of business /activity/profile /serivce or goods provided  and Select the best fit for 'taxpayer_classification' from the provided list.
    3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
    4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts mentioned after the audit para headings in the text.Convert into the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**
    5.  If a value is not found, use null. All monetary values must be numbers (float).
    6.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].
    
    DAR Text Content:
    --- START OF DAR TEXT ---
    {text_content}
    --- END OF DAR TEXT ---

    Provide ONLY the JSON object as your response. Do not include any explanatory text.
    """

    # Define models to try in order of preference
    models_to_try = [("qwen/qwen3-coder:free", "Qwen3 Coder"), 
        ("deepseek/deepseek-r1:free", "DeepSeek R1"),
        
        ("google/gemini-2.0-flash-exp:free", "Gemini 2.0 Flash")
    ]
    
    content_str_for_return = ""
    all_errors = []
    n=1
    for model_id, model_name in models_to_try:
        
        st.info(f"🤖 Trying AI Model {n}...")
        n=n+1
        
        content_str, error = try_openrouter_model(model_id, prompt, openrouter_api_key)
        
        if error is None:
            # Success! Process the response
            st.success(f"✅ Successfully got response from Model {n} ")
            content_str_for_return = content_str
            
            try:
                # Clean up response
                if content_str.strip().startswith("```json"):
                    content_str = content_str.strip()[7:-3].strip()
                elif content_str.strip().startswith("```"):
                    content_str = content_str.strip()[3:-3].strip()
                
                if not content_str:
                    all_errors.append(f"{model_name}: Empty response")
                    continue
                
                # Parse JSON
                json_data = json.loads(content_str)
                
                # Show debug info
                with st.expander(f"🔍 Raw {model_name} Response", expanded=False):
                    st.text_area("Raw Response:", content_str_for_return, height=200, disabled=True)
                
                return ParsedDARReport(**json_data)
                
            except json.JSONDecodeError as e:
                error_msg = f"Model {n} JSON decode error: {e}. Raw response: {content_str[:500]}..."
                all_errors.append(error_msg)
                st.warning(f"⚠️ {model_name} returned invalid JSON, trying next model...")
                continue
            except Exception as e:
                error_msg = f"Model {n}  processing error: {e}"
                all_errors.append(error_msg)
                st.warning(f"⚠️ Error processing {model_name} response, trying next model...")
                continue
        else:
            # Model failed
            all_errors.append(f"{model_name}: {error}")
            if "rate" in error.lower() and "limit" in error.lower():
                st.warning(f"⚠️ Model {n}  is rate limited, trying next model...")
            else:
                st.warning(f"⚠️ Model {n}  failed: {error}")
    
    # All models failed
    combined_errors = " | ".join(all_errors)
    st.error(f"❌ All models failed. Errors: {combined_errors}")
    return ParsedDARReport(parsing_errors=f"All models failed: {combined_errors}")

def get_para_classifications_from_llm(audit_para_headings: List[str]) -> Tuple[List[str], str]:
    """
    Calls multiple LLM APIs to classify audit para headings with fallback strategy.
    Returns a tuple: (list_of_codes, error_message_or_none).
    """
    openrouter_api_key = st.secrets.get("openrouter_api_key", "")
    if not openrouter_api_key:
        return [], "OpenRouter API key not found."

    formatted_observations = "\n".join([f"{i+1}. {heading}" for i, heading in enumerate(audit_para_headings)])
    user_prompt = f"Here are the audit observations to classify:\n{formatted_observations}"
    
    # Define models for classification
    classification_models = [("qwen/qwen3-coder:free", "Qwen3 Coder"),
        ("deepseek/deepseek-r1:free", "DeepSeek R1"),
        
        ("google/gemini-2.0-flash-exp:free", "Gemini 2.0 Flash")
    ]
    
    all_errors = []
    
    for model_id, model_name in classification_models:
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_api_key}"},
                data=json.dumps({
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ]
                }),
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()
                content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()

                if not content_str:
                    all_errors.append(f"{model_name}: Empty response")
                    continue

                # Parse classifications
                classifications = [code.strip() for code in content_str.split(',')]

                if len(classifications) != len(audit_para_headings):
                    error_msg = f"{model_name}: Classification count mismatch. Expected {len(audit_para_headings)}, got {len(classifications)}."
                    all_errors.append(error_msg)
                    continue

                st.success(f"✅ Classification successful with {model_name}")
                
                # Show debug info
                with st.expander(f"🏷️ {model_name} Classification Response", expanded=False):
                    st.text_area("Classification Response:", content_str, height=100, disabled=True)
                
                return classifications, None

            elif response.status_code == 429:
                error_msg = f"Model {n} : Rate limited"
                all_errors.append(error_msg)
                st.warning(f"⚠️ Model {n} is rate limited, trying next model...")
                continue
            else:
                error_msg = f"{model_name}: API Error {response.status_code} - {response.text}"
                all_errors.append(error_msg)
                continue

        except requests.exceptions.Timeout:
            error_msg = f"{model_name}: Timeout error"
            all_errors.append(error_msg)
            continue
        except requests.exceptions.RequestException as e:
            error_msg = f"{model_name}: Network error - {e}"
            all_errors.append(error_msg)
            continue
        except Exception as e:
            error_msg = f"{model_name}: Unexpected error - {e}"
            all_errors.append(error_msg)
            continue

    # All models failed
    combined_errors = " | ".join(all_errors)
    st.error(f"❌ All classification models failed: {combined_errors}")
    return [], f"All models failed: {combined_errors}"
    
# # dar_processor.py
# import pdfplumber
# import google.generativeai as genai
# import json
# import requests
# import streamlit as st
# from typing import List, Dict, Any, Tuple
# from models import ParsedDARReport, DARHeaderSchema, AuditParaSchema
# from config import BATCH_SYSTEM_PROMPT, TAXPAYER_CLASSIFICATION_OPTIONS

# def preprocess_pdf_text(pdf_path_or_bytes) -> str:
#     """
#     Extracts all text from all pages of the PDF using pdfplumber,
#     attempting to preserve layout for better LLM understanding.
#     """
#     processed_text_parts = []
#     try:
#         with pdfplumber.open(pdf_path_or_bytes) as pdf:
#             for i, page in enumerate(pdf.pages):
#                 page_text = page.extract_text(x_tolerance=2, y_tolerance=2, layout=True)
#                 if page_text is None:
#                     page_text = f"[INFO: Page {i + 1} yielded no text directly]"
#                 else:
#                     page_text = page_text.replace("None", "")
#                 processed_text_parts.append(f"\n--- PAGE {i + 1} ---\n{page_text}")
#         full_text = "".join(processed_text_parts)
#         return full_text
#     except Exception as e:
#         error_msg = f"Error processing PDF with pdfplumber: {type(e).__name__} - {e}"
#         print(error_msg)
#         return error_msg

# def get_structured_data_from_llm(text_content: str) -> ParsedDARReport:
#     """
#     Calls the OpenRouter API with the PDF text and parses the response.
#     Returns a ParsedDARReport object.
#     """
#     if text_content.startswith("Error processing PDF"):
#         return ParsedDARReport(parsing_errors=text_content)

#     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
#     if not openrouter_api_key:
#         error_msg = "OpenRouter API key not found in Streamlit secrets."
#         return ParsedDARReport(parsing_errors=error_msg)

#     prompt = f"""
#     You are an expert GST audit report analyst. Based on the following text from a Departmental Audit Report (DAR),
#     extract the specified information and structure it as a JSON object.

#     The JSON object should follow this structure precisely:
#     {{
#       "header": {{
#         "audit_group_number": "integer or null (e.g., 'Group-VI' becomes 6)",
#         "gstin": "string or null", "trade_name": "string or null", "category": "string ('Large', 'Medium', 'Small') or null",
#         "taxpayer_classification": "string or null. Choose one from the following list: {TAXPAYER_CLASSIFICATION_OPTIONS}",
#         "total_amount_detected_overall_rs": "float or null (in Rupees)",
#         "total_amount_recovered_overall_rs": "float or null (in Rupees)",
#         "risk_flags": "list of strings or null (e.g., ['P1', 'P04', 'P21'])"
#       }},
#       "audit_paras": [
#         {{
#           "audit_para_number": "integer or null (e.g., 'Para-1' becomes 1)",
#           "audit_para_heading": "string or null (title of the para)",
#           "revenue_involved_rs": "float or null ( in RUPEES)",
#           "revenue_recovered_rs": "float or null ( in RUPEES)",
#           "status_of_para": "string or null ('Agreed and Paid', 'Agreed yet to pay', 'Partially agreed and paid', 'Partially agreed, yet to pay', 'Not agreed')"
#         }}
#       ],
#       "parsing_errors": "string or null"
#     }}

#     Key Instructions:
#     1.  Header Info: Find all header fields.
#     2.  Taxpayer Classification: Identify the taxpayer nature of business /activity/profile /serivce or goods provided  and Select the best fit for 'taxpayer_classification' from the provided list.
#     3.  Risk Flags: Find all risk parameter codes mentioned, which look like P1, P2, P3... P34. Ignore any numbers in parentheses like P1(1). Collect only the codes (e.g., "P1").
#     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts in the text. These amounts are often written as 'Rs. X,XX,XXX' or 'in Rupees'. Extract ONLY the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**.
#     #4.  **CRITICAL FOR REVENUE**: For `revenue_involved_rs` and `revenue_recovered_rs`, find the corresponding monetary amounts mentioned after the audit para headings in the text.Convert into the numeric value as a float. **For example, if the text says 'revenue involved is Rs. 5,50,000', the value must be `550000.0`**
#     5.  If a value is not found, use null. All monetary values must be numbers (float).
#     6.  The 'audit_paras' list should contain one object per para. If none found, provide an empty list [].
    
#     DAR Text Content:
#     --- START OF DAR TEXT ---
#     {text_content}
#     --- END OF DAR TEXT ---

#     Provide ONLY the JSON object as your response. Do not include any explanatory text.
#     """

#     content_str_for_return = ""
#     try:
#         response = requests.post(
#             url="https://openrouter.ai/api/v1/chat/completions",
#             headers={"Authorization": f"Bearer {openrouter_api_key}"},
#             data=json.dumps({
#                 "model": "deepseek/deepseek-r1:free",
#                 "messages": [{"role": "user", "content": prompt}]
#             })
#         )
#         if response.status_code != 200:
#             error_text = f"API Error from OpenRouter: {response.status_code} - {response.text}"
#             return ParsedDARReport(parsing_errors=error_text)

#         response_data = response.json()
#         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
#         content_str_for_return = content_str
        
#         if content_str.strip().startswith("```json"):
#             content_str = content_str.strip()[7:-3].strip()
#         elif content_str.strip().startswith("```"):
#              content_str = content_str.strip()[3:-3].strip()
        
#         if not content_str:
#             return ParsedDARReport(parsing_errors="LLM returned an empty response.")
        
#         json_data = json.loads(content_str)
#         return ParsedDARReport(**json_data)
#     except requests.exceptions.RequestException as e:
#         return ParsedDARReport(parsing_errors=f"Network error calling OpenRouter API: {e}")
#     except json.JSONDecodeError as e:
#         err_msg = f"LLM output was not valid JSON: {e}. Raw response: {content_str_for_return[:500]}..."
#         return ParsedDARReport(parsing_errors=err_msg)
#     except Exception as e:
#         return ParsedDARReport(parsing_errors=f"An unexpected error occurred: {e}")

# def get_para_classifications_from_llm(audit_para_headings: List[str]) -> (List[str], str):
#     openrouter_api_key = st.secrets.get("openrouter_api_key", "")
#     if not openrouter_api_key:
#         return [], "OpenRouter API key not found."
#     formatted_observations = "\n".join([f"{i+1}. {heading}" for i, heading in enumerate(audit_para_headings)])
#     user_prompt = f"Here are the audit observations to classify:\n{formatted_observations}"
#     try:
#         response = requests.post(
#             url="https://openrouter.ai/api/v1/chat/completions",
#             headers={"Authorization": f"Bearer {openrouter_api_key}"},
#             data=json.dumps({
#                 "model": "deepseek/deepseek-r1:free",
#                 "messages": [
#                     {"role": "system", "content": BATCH_SYSTEM_PROMPT},
#                     {"role": "user", "content": user_prompt}
#                 ]
#             })
#         )
#         if response.status_code != 200:
#             return [], f"API Error from OpenRouter: {response.status_code} - {response.text}"
#         response_data = response.json()
#         content_str = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
#         if not content_str:
#             return [], "LLM returned an empty response for classification."
#         classifications = [code.strip() for code in content_str.split(',')]
#         if len(classifications) != len(audit_para_headings):
#             error_msg = f"Classification count mismatch. Expected {len(audit_para_headings)}, but got {len(classifications)}. Raw response: '{content_str}'"
#             return classifications, error_msg
#         return classifications, None
#     except requests.exceptions.RequestException as e:
#         return [], f"Network error during classification: {e}"
#     except Exception as e:
#         return [], f"An unexpected error occurred during classification: {e}"# # dar_processor.py


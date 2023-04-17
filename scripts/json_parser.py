import json, re
from typing import Any, Dict, Union
from call_ai_function import call_ai_function
from config import Config
from json_utils import correct_json

cfg = Config()

JSON_SCHEMA = """
{
    "command": {
        "name": "command name",
        "args":{
            "arg name": "value"
        }
    },
    "thoughts":
    {
        "text": "thought",
        "reasoning": "reasoning",
        "plan": "- short bulleted\n- list that conveys\n- long-term plan",
        "criticism": "constructive self-criticism",
        "speak": "thoughts summary to say to user"
    }
}
"""

def fixJSON(jsonStr):
    # Substitue all the backslash from JSON string.
    jsonStr = jsonStr.replace('\t', '').replace('\\n', '\n')
    jsonStr = re.sub(r'\\', '', jsonStr)
    try:
        json.loads(jsonStr)
        return jsonStr
    except ValueError:
        while True:
            # Search json string specifically for '"'
            b = re.search(r'[\w|"]\s?(")\s?[\w|"]', jsonStr)
            keys_with_invalid_string = re.search("(?:((\\')\w+(\\'):))", jsonStr)

            # If we don't find any the we come out of loop
            if not b and not keys_with_invalid_string:
                break

            # Get the location of \"
            if b is not None:
                s, e = b.span(1)
                c = jsonStr[s:e]
                c = c.replace('"',"'")
                jsonStr = jsonStr[:s] + c + jsonStr[e:]
            
            if keys_with_invalid_string is not None:
                f, l = keys_with_invalid_string.span(1) 
                key_index = jsonStr[f:l]
                key_index = key_index.replace("'", '"')
                jsonStr = jsonStr[:f] + key_index + jsonStr[l:]
        return jsonStr

def fix_and_parse_json(    
    json_str: str,
    try_to_fix_with_gpt: bool = True
) -> Union[str, Dict[Any, Any]]:
    """Fix and parse JSON string"""
    try:
        json_str = fixJSON(json_str)
        return json.loads(json_str)
    except json.JSONDecodeError as _:  # noqa: F841
        try:
            json_str = correct_json(json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as _:  # noqa: F841
            pass
    # Let's do something manually:
    # sometimes GPT responds with something BEFORE the braces:
    # "I'm sorry, I don't understand. Please try again."
    # {"text": "I'm sorry, I don't understand. Please try again.",
    #  "confidence": 0.0}
    # So let's try to find the first brace and then parse the rest
    #  of the string
    try:
        brace_index = json_str.index("{")
        json_str = json_str[brace_index:]
        last_brace_index = json_str.rindex("}")
        json_str = json_str[:last_brace_index+1]
        return json.loads(json_str)
    except ValueError:
        loaded_json = {"string_response": json_str}
        return loaded_json
    except json.JSONDecodeError as e:  # noqa: F841
        if try_to_fix_with_gpt:
            print("Warning: Failed to parse AI output, attempting to fix."
                  "\n If you see this warning frequently, it's likely that"
                  " your prompt is confusing the AI. Try changing it up"
                  " slightly.")
            # Now try to fix this up using the ai_functions
            ai_fixed_json = fix_json(json_str, JSON_SCHEMA)

            if ai_fixed_json != "failed":
                return json.loads(ai_fixed_json)
            else:
                # This allows the AI to react to the error message,
                #   which usually results in it correcting its ways.
                print("Failed to fix ai output, telling the AI.")
                return json_str
        else:
            raise e
            
        
def fix_json(json_str: str, schema: str) -> str:
    """Fix the given JSON string to make it parseable and fully complient with the provided schema."""
    
    # Try to fix the JSON using gpt:
    function_string = "def fix_json(json_str: str, schema:str=None) -> str:"
    args = [f"'''{json_str}'''", f"'''{schema}'''"]
    description_string = "Fixes the provided JSON string to make it parseable"\
        " and fully complient with the provided schema.\n If an object or"\
        " field specified in the schema isn't contained within the correct"\
        " JSON, it is ommited.\n This function is brilliant at guessing"\
        " when the format is incorrect."

    # If it doesn't already start with a "`", add one:
    if not json_str.startswith("`"):
        json_str = "```json\n" + json_str + "\n```"
    result_string = call_ai_function(
        function_string, args, description_string, model=cfg.fast_llm_model
    )
    if cfg.debug:
        print("------------ JSON FIX ATTEMPT ---------------")
        print(f"Original JSON: {json_str}")
        print("-----------")
        print(f"Fixed JSON: {result_string}")
        print("----------- END OF FIX ATTEMPT ----------------")

    try:
        result_string = fixJSON(result_string)  # just check the validity
        return json.loads(result_string)
    except:  # noqa: E722
        # Get the call stack:
        # import traceback
        # call_stack = traceback.format_exc()
        # print(f"Failed to fix JSON: '{json_str}' "+call_stack)
        return "failed"

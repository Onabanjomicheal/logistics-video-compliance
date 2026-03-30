import operator
from typing import Annotated, List, Dict,  Optional, Any, TypedDict

#Define the schema for a single compliance result

class ComplianceIssue(TypedDict):
    category : str
    description : str # specific detail of violation
    severity : str # CRITICAL | WARNING
    timestamp : Optional[str]

# define global graph state

class VideoAuditState(TypedDict):
    '''
    Defines the data schema for langgraph execution content
    Main containers: holds all the information about the audit
    right from the initail URL to the final report
    '''
    # input parameters
    video_url : str
    video_id : str
    sample_interval_sec : Optional[int]
    max_frames : Optional[int]

    # ingestion and extraction data
    frames_analyzed : Optional[int]
    scene_summary : Optional[str]
    ocr_text : List[str]
    video_metadata : Dict[str, Any]

    # analysis output
    compliance_results : Annotated[List[ComplianceIssue], operator.add]
    rules_used : List[str]

    # final deliverables

    final_status : str # PASS | FAIL
    final_report : str # Markdown format

    # system observability
    # errors : API timeouts, system level errors
    errors : Annotated[List[str], operator.add]

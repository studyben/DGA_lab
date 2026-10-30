export type InputFormat='XLSX'|'CSV_PAIR';
export type Purpose='HISTORICAL'|'DAILY';
export type FileRole='WORKBOOK'|'SAMPLES'|'TESTS';
export type SourceLab={id:string;display_name:string;source_kind:'IN_HOUSE'|'THIRD_PARTY'};
export type SourceDecision={key:string;reason:string}&(
  {decision:'NEW';proposed_name:string;source_kind:SourceLab['source_kind'];confirm_distinct:true;candidate_digest:string}|
  {decision:'REFERENCE';source_lab_id:string});
export type CreateInput={format_version:1;input_format:InputFormat;purpose:Purpose;source_timezone?:string|null;
  source_timezone_confirmed:boolean;source_labs:SourceDecision[]};
export type RevisionInput={expected_revision:number;reason:string;metadata?:{purpose?:Purpose;source_timezone?:string|null;
  source_timezone_confirmed?:boolean};source_labs?:SourceDecision[];active_files?:Partial<Record<FileRole,string>>;changes?:{row_id:string;values:Record<string,string|boolean|number|null>}[]};
export type OriginalFile={id:string;batch_id:string;role:FileRole;state:'PENDING'|'RECEIVED'|'RETRYABLE';active:boolean;
  filename:string;content_type:string;byte_size:number;sha256:string;received_by:string;reserved_at:string;
  received_at:string|null;failure_code:string|null};
export type Binding={source_lab_key:string;source_lab_id:string;display_name:string;source_kind:SourceLab['source_kind'];
  reason:string;confirmed_by:string;confirmed_at:string};
export type Batch={id:string;format_version:1;input_format:InputFormat;purpose:Purpose;source_timezone:string|null;
  source_timezone_confirmed:boolean;revision:number;business_state:'STAGED';validation_state:string;
  manifest_state?:'EMPTY'|'PARTIAL'|'COMPLETE';source_labs?:Binding[];active_files?:Pick<OriginalFile,'id'|'role'|'filename'|'byte_size'|'sha256'>[];
  created_at:string;updated_at:string;created_by:string;current_job?:ValidationJob|null;validation_current?:boolean;stale?:boolean;summary?:ValidationSummary};
export type Operation={state:'PENDING'|'RETRYABLE'|'COMPLETED'|'REJECTED';action:'CREATE'|'RECEIVE'|'REVISE'|'VALIDATE';
  batch_id:string|null;result:{outcome?:string;batch_id?:string;file_id?:string;job_id?:string;applied_revision?:number;
    code?:string;status?:number;details?:unknown}|null;error_code:string|null};
export type Page<T>={items:T[];total:number;page:number;page_size:number};
export type Revision={id:string;revision:number;actor_id:string;display_name:string;occurred_at:string;reason:string;
  before_value:unknown;after_value:unknown;event_id?:string;change_kind?:'BATCH'|'ROW';row_id?:string;sheet?:string;row_number?:number;row_change_count?:number};
export type SourcePage=Page<SourceLab>&{exact_name_total?:number;candidate_digest?:string};
export type UploadMetadata={batch_id:string;role:FileRole;filename:string;content_type:string;byte_size:number;sha256:string};
export type Receipt={operation:Operation;file:OriginalFile;batch_revision:number;in_flight:boolean};
export type MutationResult={operation:Operation;batch:Batch};


export type DurableInputRejection=Operation&{state:'REJECTED';action:'CREATE'|'REVISE'|'VALIDATE';batch_id:null;
  result:{code:'invalid_import_input';status:422;details:null};error_code:null};



export type ValidationInput={expected_revision:number};
export type Severity='ERROR'|'WARNING'|'INFO';
export type IssueCounts=Record<Severity,number>;
export type ValidationJob={id:string;batch_id:string;input_revision:number;state:'QUEUED'|'RUNNING'|'COMPLETE'|'FAILED'|'SUPERSEDED';
  phase:string;progress_done:number;progress_total:number;attempt:number;error_code:string|null;
  created_at:string;started_at:string|null;completed_at:string|null;validation_as_of?:string|null;
  catalog_fingerprint?:string|null;file_issue_count?:number};
export type ValidationSummary={sample_count?:number;test_count?:number;unassigned_test_count?:number;
  error_count?:number;warning_count?:number;checked_sample_count?:number;last_job_id?:string;input_revision?:number};
export type TemporalEvidence={raw:unknown;precision:'DATE'|'INSTANT'|'MISSING'|'UNRESOLVED';business_date:string|null;
  local_time:string|null;source_timezone:string|null;explicit_offset:string|null;utc_instant:string|null;issue_codes:string[]};
export type MeasurementEvidence={raw_value:unknown;qualifier:string|null;value:string|null;unit:string|null;source_precision:string|null};
export type StagedIssue={version:1;id:string;code:string;severity:Severity;file_id:string;sheet:string|null;
  row_number:number|null;field:string|null;row_id:string|null;external_sample_id?:string|null;external_test_id?:string|null;
  raw_value:unknown;message:string;suggestion:string;sample_row_id?:string|null;
  sample_page?:number|null;test_page?:number|null;unassigned_page?:number|null};
export type ParsedEvidence={temporal?:Record<string,TemporalEvidence>;measurements?:Record<string,MeasurementEvidence>;
  reports?:{filename:string;state:'DECLARED_NOT_PROVIDED'}[];source_evidence?:Record<string,unknown>;
  asset?:Record<string,unknown>|null;[key:string]:unknown};
export type StagedRow={id:string;file_id:string;batch_id:string;sheet:'油样信息'|'检测结果';row_number:number;
  raw_values:Record<string,unknown>;raw_cell_types:Record<string,string>;overrides:Record<string,unknown>;
  reviewed_values:Record<string,unknown>;parsed_values:ParsedEvidence;issues:StagedIssue[];parsed_revision:number|null;
  sample_row_id:string|null;source_lab_id:string|null;external_sample_id:string|null;external_test_id:string|null;
  stale:boolean;related_test_count:number;issue_counts:IssueCounts};
export type SamplesPage=Page<StagedRow>&{unassigned_test_total:number;file_issues_summary:IssueCounts;
  validation_current:boolean;stale:boolean;result_job_id:string|null};
export type SampleDetail={sample:StagedRow;tests:Page<StagedRow>;validation_current:boolean;stale:boolean};
export type UnassignedPage=Page<StagedRow>&{validation_current:boolean;stale:boolean};
export type IssuesPage=Page<StagedIssue>&{severity_counts:IssueCounts;stale:boolean};
export type ValidationResult=MutationResult&{job:ValidationJob};

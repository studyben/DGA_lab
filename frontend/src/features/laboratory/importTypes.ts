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
  source_timezone_confirmed?:boolean};source_labs?:SourceDecision[];active_files?:Partial<Record<FileRole,string>>};
export type OriginalFile={id:string;batch_id:string;role:FileRole;state:'PENDING'|'RECEIVED'|'RETRYABLE';active:boolean;
  filename:string;content_type:string;byte_size:number;sha256:string;received_by:string;reserved_at:string;
  received_at:string|null;failure_code:string|null};
export type Binding={source_lab_key:string;source_lab_id:string;display_name:string;source_kind:SourceLab['source_kind'];
  reason:string;confirmed_by:string;confirmed_at:string};
export type Batch={id:string;format_version:1;input_format:InputFormat;purpose:Purpose;source_timezone:string|null;
  source_timezone_confirmed:boolean;revision:number;business_state:'STAGED';validation_state:string;
  manifest_state?:'EMPTY'|'PARTIAL'|'COMPLETE';source_labs?:Binding[];active_files?:Pick<OriginalFile,'id'|'role'|'filename'|'byte_size'|'sha256'>[];
  created_at:string;updated_at:string;created_by:string};
export type Operation={state:'PENDING'|'RETRYABLE'|'COMPLETED'|'REJECTED';action:'CREATE'|'RECEIVE'|'REVISE';
  batch_id:string|null;result:{outcome?:string;batch_id?:string;file_id?:string;applied_revision?:number;
    code?:string;status?:number;details?:unknown}|null;error_code:string|null};
export type Page<T>={items:T[];total:number;page:number;page_size:number};
export type Revision={id:string;revision:number;actor_id:string;display_name:string;occurred_at:string;reason:string;
  before_value:unknown;after_value:unknown};
export type SourcePage=Page<SourceLab>&{exact_name_total?:number;candidate_digest?:string};
export type UploadMetadata={batch_id:string;role:FileRole;filename:string;content_type:string;byte_size:number;sha256:string};
export type Receipt={operation:Operation;file:OriginalFile;batch_revision:number;in_flight:boolean};
export type MutationResult={operation:Operation;batch:Batch};


export type DurableInputRejection=Operation&{state:'REJECTED';action:'CREATE'|'REVISE';batch_id:null;
  result:{code:'invalid_import_input';status:422;details:null};error_code:null};


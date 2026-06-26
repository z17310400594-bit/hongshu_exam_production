/** Raw certificate record from GET /query/certs */
export interface CertRecord {
  cert_id: string
  cert_name: string
  short_name: string
  issuing_authority: string
  profession_category: string
  /** Nearest future exam date (YYYY-MM-DD), or null if no upcoming exam */
  exam_date: string | null
}

/** GET /query/certs response envelope */
export interface CertsResponse {
  certs: CertRecord[]
  count: number
}

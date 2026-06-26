import { useState, useEffect } from 'react'
import type { ExamCategory } from '@/types/topic-finder'
import type { CertRecord } from '@/types/policy'
import { fetchCerts } from '@/services/policyApi'

function certToCategory(cert: CertRecord): ExamCategory {
  return {
    id: cert.cert_name,
    name: cert.cert_name,
    examDate: cert.exam_date ?? '',
    keywords: [],
    subjects: [],
  }
}

/**
 * Hook: certificate list for the exam dropdown, from policy-api DB only.
 * Returns empty array while loading, DB certs on success.
 */
export function useCertPresets(): { certOptions: ExamCategory[]; loading: boolean } {
  const [certOptions, setCertOptions] = useState<ExamCategory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    fetchCerts()
      .then(({ certs }) => {
        if (cancelled) return
        setCertOptions(certs.map(certToCategory))
      })
      .catch(() => {
        // API unavailable — keep empty list
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [])

  return { certOptions, loading }
}

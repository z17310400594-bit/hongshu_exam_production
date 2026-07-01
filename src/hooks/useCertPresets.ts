import { useCallback, useState, useEffect } from 'react'
import type { ExamCategory } from '@/types/topic-finder'
import type { CertRecord } from '@/types/policy'
import { fetchCerts as fetchLegacyCerts } from '@/services/policyApi'
import { EXAM_CATEGORIES } from '@/constants/exam-categories'
import {
  fetchV2CertificateExamDate,
  fetchV2Certificates,
  pickExamDateFromCertificate,
  useV2CertificateApi,
} from '@/services/certificateApi'
import type { V2CertificateSummary } from '@/types/api'

function certToCategory(cert: CertRecord): ExamCategory {
  return {
    id: cert.cert_name,
    name: cert.cert_name,
    examDate: cert.exam_date ?? '',
    keywords: [],
    subjects: [],
  }
}

function v2CertToCategory(cert: V2CertificateSummary): ExamCategory {
  return {
    id: cert.code,
    name: cert.name,
    examDate: pickExamDateFromCertificate(cert),
    keywords: cert.aliases ?? [],
    subjects: [],
  }
}

/**
 * Hook: certificate list for the exam dropdown.
 *
 * WP13: use V2 certificates by default.  Set
 * TARO_APP_USE_V2_CERTIFICATE_API=false to fall back to the legacy policy-api
 * without touching the page component.
 */
export function useCertPresets(): {
  certOptions: ExamCategory[]
  loading: boolean
  isV2Enabled: boolean
  error: string
  resolveExamDate: (categoryId: string) => Promise<string>
} {
  const [certOptions, setCertOptions] = useState<ExamCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const isV2Enabled = useV2CertificateApi()

  useEffect(() => {
    let cancelled = false

    const request = isV2Enabled
      ? fetchV2Certificates().then(({ items }) => items.map(v2CertToCategory))
      : fetchLegacyCerts().then(({ certs }) => certs.map(certToCategory))

    request
      .then(options => {
        if (cancelled) return
        setError('')
        if (isV2Enabled) {
          setCertOptions(options)
        } else {
          setCertOptions(options.length > 0 ? options : EXAM_CATEGORIES)
        }
      })
      .catch(() => {
        if (cancelled) return
        if (isV2Enabled) {
          setCertOptions([])
          setError('数据库证书列表加载失败，请检查后端 /api/v2/certificates')
        } else {
          setCertOptions(EXAM_CATEGORIES)
          setError('旧证书接口加载失败，已使用本地预设')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [isV2Enabled])

  const resolveExamDate = useCallback(async (categoryId: string): Promise<string> => {
    const current = certOptions.find(cat => cat.id === categoryId)
    if (!isV2Enabled) return current?.examDate ?? ''
    try {
      return await fetchV2CertificateExamDate(categoryId)
    } catch {
      return current?.examDate ?? ''
    }
  }, [certOptions, isV2Enabled])

  return { certOptions, loading, isV2Enabled, error, resolveExamDate }
}

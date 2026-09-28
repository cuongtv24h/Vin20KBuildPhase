import { createContext, useContext } from 'react'
import type { SourceCoordinate } from '@pricepolicy/api-client/contracts'

export interface EvidenceTarget {
  title: string
  source: SourceCoordinate | null
  ruleCode?: string | null
}

export const EvidenceContext = createContext<(target: EvidenceTarget) => void>(() => undefined)

/** Mở panel chứng cứ từ bất kỳ dòng breakdown / claim nào bên trong EvidenceProvider. */
export const useOpenEvidence = () => useContext(EvidenceContext)

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { learnerApi } from '../../api'
import type { LearnerListParams } from '../../api/learner'

export function useLearners(params?: LearnerListParams) {
  const page = params?.page ?? 1
  const pageSize = params?.pageSize ?? 10

  return useQuery({
    queryKey: ['learners', { page, pageSize, ...params }],
    queryFn: async () => {
      return learnerApi.getList({ ...params, page, pageSize })
    },
    placeholderData: keepPreviousData,
    staleTime: 15 * 1000,
  })
}

export function useLearnerDetail(id: number | null) {
  return useQuery({
    queryKey: ['learner', id],
    queryFn: async () => {
      if (id === null) return null
      return learnerApi.getById(id)
    },
    enabled: id !== null,
  })
}

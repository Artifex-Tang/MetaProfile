import { topicApi } from './client'
import type { TopicItem, TopicDetail, FeedbackResponse, SearchResultList } from './types'

export const topicService = {
  list: (page = 1, pageSize = 10, status?: string) =>
    topicApi.get<SearchResultList<TopicItem>>('/api/v1/topics/list', {
      params: { page, page_size: pageSize, status },
    }).then(r => r.data),

  getById: (id: string) =>
    topicApi.get<TopicDetail>(`/api/v1/topics/${id}`).then(r => r.data),

  feedback: (topicId: string, rating: 'accept' | 'reject' | 'revise', score: number, comments?: string) =>
    topicApi.post<FeedbackResponse>(`/api/v1/topics/${topicId}/feedback`, {
      rating, score, comments: comments ?? null, operator: 'user',
    }).then(r => r.data),

  generate: (targetCount: number, periodFrom?: string, periodTo?: string) =>
    topicApi.post('/api/v1/topics/generate', {
      target_count: targetCount, period_from: periodFrom, period_to: periodTo,
    }).then(r => r.data),
}

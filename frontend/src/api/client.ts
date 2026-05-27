import axios from 'axios'

const make = (base: string) => axios.create({ baseURL: base, timeout: 15000 })

export const techApi      = make('/api-tech')
export const projectApi   = make('/api-project')
export const orgApi       = make('/api-org')
export const personApi    = make('/api-person')
export const scanApi      = make('/api-scan')
export const discoveryApi = make('/api-discovery')
export const topicApi     = make('/api-topic')
export const settingsApi  = make('/api-settings')

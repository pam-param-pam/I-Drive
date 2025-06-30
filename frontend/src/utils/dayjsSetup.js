import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import localizedFormat from 'dayjs/plugin/localizedFormat'

// Import locales you want to support
import 'dayjs/locale/en'
import 'dayjs/locale/pl'

// Extend dayjs with the plugins
dayjs.extend(relativeTime)
dayjs.extend(localizedFormat)

dayjs.locale('en')

export default dayjs
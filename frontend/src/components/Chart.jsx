import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

/** 轻量 ECharts 封装：负责初始化、随容器自适应、卸载时销毁 */
export default function Chart({ option, height = 280, style }) {
  const holder = useRef(null)
  const chart = useRef(null)

  useEffect(() => {
    if (!holder.current) return undefined
    chart.current = echarts.init(holder.current)
    const observer = new ResizeObserver(() => {
      if (chart.current) chart.current.resize()
    })
    observer.observe(holder.current)
    return () => {
      observer.disconnect()
      if (chart.current) {
        chart.current.dispose()
        chart.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (chart.current && option) chart.current.setOption(option, true)
  }, [option])

  return <div ref={holder} style={{ width: '100%', height, ...style }} />
}

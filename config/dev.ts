import type { UserConfigExport } from "@tarojs/cli"

export default {
   logger: {
    quiet: false,
    stats: true
  },
  mini: {},
  h5: {
    devServer: {
      host: '0.0.0.0', // 监听所有网络接口，同网络下其他设备可访问
    },
  }
} satisfies UserConfigExport<'webpack5'>

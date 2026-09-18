import type { FullConfig } from '@nekosu/maa-tools'

const config: FullConfig = {
  cwd: import.meta.dirname,
  maaVersion: 'latest',
  interfacePath: 'assets/interface.json',
  check: {
    override: {
      // 生成的多人节点把同一停止节点同时放在 next（无匹配兜底）
      // 和 on_error（超时兜底）中；两条路径有意保留。离线检查会单独
      // 验证每个 next 列表没有重复项。
      'duplicate-next': 'ignore',
      // 忽略 mpe-config 带来的报错
      // ignore warning caused by mpe-config
      // 'mpe-config': 'ignore'
    }
  }
}

export default config

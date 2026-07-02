import type { NodePort, NodeSpec } from '@/types'

export const GROUP_MERGE_NODE_TYPE = 'eeg/group/merge'

export function allowsMultipleInputLinks(
  spec: NodeSpec | null | undefined,
  port: NodePort | null | undefined,
): boolean {
  return Boolean(
    spec?.type === GROUP_MERGE_NODE_TYPE
      && port?.name === 'input'
      && port?.cardinality === 'one_or_many',
  )
}

export function canonicalInputPortName(spec: NodeSpec | null | undefined, portName: string | null | undefined): string {
  const name = String(portName || 'input')
  const exact = spec?.inputs?.find((port) => port.name === name)
  if (exact) return exact.name
  const match = name.match(/^(.+)_([2-9][0-9]*)$/)
  if (!match) return name
  const base = match[1]
  const basePort = spec?.inputs?.find((port) => port.name === base)
  return allowsMultipleInputLinks(spec, basePort) ? base : name
}

export function liteGraphInputPorts(spec: NodeSpec): NodePort[] {
  return spec.inputs || []
}

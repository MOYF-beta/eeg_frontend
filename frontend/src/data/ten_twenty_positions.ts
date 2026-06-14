/**
 * 10-20 国际标准导联系统电极位置数据
 * 参考 MNE-Python spherical_1020.tsv
 * 
 * 3D 球坐标 (x, y, z) 投影到 2D 顶视图:
 *   x → 左右 (left = 负, right = 正)
 *   y → 前后 (front/鼻根 = 正, back/枕骨 = 负)
 */

export interface ElectrodePosition {
  name: string;
  x: number;  // 2D x (左右)
  y: number;  // 2D y (前后)
  z: number;  // 3D z (保留用于插值)
  theta: number; // 角度 (弧度, 从右侧逆时针)
  phi: number;   // 仰角 (弧度, 从顶部)
}

export interface TenTwentyRegion {
  name: string;
  electrodes: string[];
  color: string;
}

// 10-20 标准电极 3D 球坐标 (单位球面)
const SPHERICAL_1020_3D: Record<string, { x: number; y: number; z: number }> = {
  'C3':  { x: -0.5878, y:  0.0000, z: 0.8090 },
  'C4':  { x:  0.5878, y:  0.0000, z: 0.8090 },
  'Cz':  { x:  0.0000, y:  0.0000, z: 1.0000 },
  'F3':  { x: -0.4591, y:  0.5800, z: 0.6730 },
  'F4':  { x:  0.4591, y:  0.5800, z: 0.6730 },
  'F7':  { x: -0.7695, y:  0.5590, z: 0.3090 },
  'F8':  { x:  0.7695, y:  0.5590, z: 0.3090 },
  'Fp1': { x: -0.2939, y:  0.9045, z: 0.3090 },
  'Fp2': { x:  0.2939, y:  0.9045, z: 0.3090 },
  'Fpz': { x:  0.0000, y:  0.9511, z: 0.3090 },
  'Fz':  { x:  0.0000, y:  0.5878, z: 0.8090 },
  'O1':  { x: -0.2939, y: -0.9045, z: 0.3090 },
  'O2':  { x:  0.2939, y: -0.9045, z: 0.3090 },
  'Oz':  { x:  0.0000, y: -0.9511, z: 0.3090 },
  'P3':  { x: -0.4591, y: -0.5800, z: 0.6730 },
  'P4':  { x:  0.4591, y: -0.5800, z: 0.6730 },
  'P7':  { x: -0.7695, y: -0.5590, z: 0.3090 },
  'P8':  { x:  0.7695, y: -0.5590, z: 0.3090 },
  'Pz':  { x:  0.0000, y: -0.5878, z: 0.8090 },
  'T7':  { x: -0.9511, y:  0.0000, z: 0.3090 },
  'T8':  { x:  0.9511, y:  0.0000, z: 0.3090 },
};

// 参考点（用于头部轮廓）
const REFERENCE_POINTS: Record<string, { x: number; y: number; z: number }> = {
  'NAS': { x:  0.0000, y:  1.0000, z: 0.0000 },
  'LPA': { x: -1.0000, y:  0.0000, z: 0.0000 },
  'RPA': { x:  1.0000, y:  0.0000, z: 0.0000 },
};

/**
 * 计算球坐标的角度
 */
function cartToSph(x: number, y: number, z: number): { theta: number; phi: number } {
  const r = Math.sqrt(x * x + y * y + z * z);
  const phi = Math.acos(z / r); // 0 at top, PI at bottom
  let theta = Math.atan2(y, x);  // 0 at right (T8)
  // Normalize theta to [0, 2*PI)
  if (theta < 0) theta += 2 * Math.PI;
  return { theta, phi };
}

/**
 * 获取所有 10-20 电极的完整位置信息（2D 投影 + 3D 信息）
 */
export function getTenTwentyPositions(): ElectrodePosition[] {
  return Object.entries(SPHERICAL_1020_3D).map(([name, pos]) => {
    const { theta, phi } = cartToSph(pos.x, pos.y, pos.z);
    return {
      name,
      x: pos.x,   // 2D 左右
      y: pos.y,   // 2D 前后
      z: pos.z,   // 3D 高度
      theta,
      phi,
    };
  });
}

/**
 * 电极按脑区分组
 */
export const TEN_TWENTY_REGIONS: TenTwentyRegion[] = [
  { name: '额极 (Fp)', electrodes: ['Fp1', 'Fp2', 'Fpz'], color: '#FF6B6B' },
  { name: '额区 (F)',  electrodes: ['F3', 'F4', 'F7', 'F8', 'Fz'], color: '#4ECDC4' },
  { name: '中央 (C)',  electrodes: ['C3', 'C4', 'Cz'], color: '#45B7D1' },
  { name: '颞区 (T)',  electrodes: ['T7', 'T8'], color: '#96CEB4' },
  { name: '顶区 (P)',  electrodes: ['P3', 'P4', 'P7', 'P8', 'Pz'], color: '#FFEAA7' },
  { name: '枕区 (O)',  electrodes: ['O1', 'O2', 'Oz'], color: '#DDA0DD' },
];

/**
 * 10-20 标准导联名称列表
 */
export const TEN_TWENTY_NAMES = Object.keys(SPHERICAL_1020_3D);

/**
 * 解析通道名称: 格式 {被试编号}@{10-20标准导联名称}
 * 例如: "subject01@Cz" → { subject: "subject01", electrode: "Cz" }
 * 也支持纯 10-20 名称: "Cz" → { subject: "", electrode: "Cz" }
 */
export function parseChannelName(channelName: string): { subject: string; electrode: string } | null {
  const trimmed = channelName.trim();
  
  // 尝试匹配 {被试编号}@{电极} 格式
  const match = trimmed.match(/^(.+?)@(Fp[12z]|F[3478z]|C[34z]|P[3478z]|O[12z]|T[78])$/i);
  if (match) {
    return { subject: match[1], electrode: match[2] };
  }
  
  // 尝试匹配纯电极名称
  const electrodeMatch = trimmed.match(/^(Fp[12z]|F[3478z]|C[34z]|P[3478z]|O[12z]|T[78])$/i);
  if (electrodeMatch) {
    return { subject: '', electrode: electrodeMatch[1] };
  }
  
  return null;
}

/**
 * 生成10-20格式的通道名称
 */
export function formatTenTwentyName(subject: string, electrode: string): string {
  if (!subject) return electrode;
  return `${subject}@${electrode}`;
}

/**
 * 检查通道名是否是有效的10-20格式
 */
export function isValidTenTwentyName(channelName: string): boolean {
  return parseChannelName(channelName) !== null;
}

/**
 * 电极-设备通道映射
 */
export interface ElectrodeMapping {
  electrode: string;
  deviceId: string;
  channelIndex: number;
  channelLabel: string;
}

export interface TenTwentyDialogResult {
  subjectId: string;
  mappings: ElectrodeMapping[];
}

export interface DeviceChannelInfo {
  id: string;
  name: string;
  channelCount: number;
  channels?: Array<{ index: number; name: string; alias?: string }>;
}

export interface CategoryDefinition {
  name: string;
  color: string;
  description: string;
  subcategories: string[];
}

/**
 * Generic defaults used when no local taxonomy is configured. A deployment can
 * override these in data/local.json (served by /api/meta/taxonomy); the local
 * file is gitignored, so private business categories never enter the repo.
 */
export const CATEGORIES: CategoryDefinition[] = [
  {
    name: "产品研发",
    color: "#5B7CFA",
    description: "需求、开发、测试与发布",
    subcategories: ["需求与设计", "开发实现", "测试验证", "发布上线"],
  },
  {
    name: "客户与项目",
    color: "#22C55E",
    description: "售前方案、客户交付与技术支持",
    subcategories: ["售前方案", "客户交付", "技术支持"],
  },
  {
    name: "内容与市场",
    color: "#8B5CF6",
    description: "内容创作、市场活动与竞品研究",
    subcategories: ["内容创作", "市场活动", "竞品研究"],
  },
  {
    name: "运营与管理",
    color: "#F59E0B",
    description: "工作复盘、流程制度与团队协作",
    subcategories: ["工作复盘", "流程制度", "团队协作"],
  },
  {
    name: "其他",
    color: "#64748B",
    description: "跨部门、临时事项与其他工作",
    subcategories: ["跨部门", "临时事项"],
  },
];

export const WORK_TYPES: string[] = [
  "方案与售前",
  "内容创作",
  "技术研发",
  "测试验证",
  "客户交付",
  "技术支持",
  "会议与培训",
  "运营支持",
  "竞品研究",
  "复盘与管理",
  "其他",
];

export async function loadTaxonomy(): Promise<void> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch("/api/meta/taxonomy", {
      signal: controller.signal,
    });
    if (!response.ok) return;
    const data = await response.json();
    if (Array.isArray(data.categories) && data.categories.length) {
      CATEGORIES.splice(0, CATEGORIES.length, ...data.categories);
    }
    if (Array.isArray(data.work_types) && data.work_types.length) {
      WORK_TYPES.splice(0, WORK_TYPES.length, ...data.work_types);
    }
  } catch {
    // Keep the built-in defaults when the API is unavailable.
  } finally {
    window.clearTimeout(timer);
  }
}

export function categoryColor(name?: string | null): string {
  return CATEGORIES.find((item) => item.name === name)?.color || "#64748B";
}

export function subcategoriesFor(name?: string | null): string[] {
  return CATEGORIES.find((item) => item.name === name)?.subcategories || [];
}

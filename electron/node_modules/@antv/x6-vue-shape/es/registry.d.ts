export type VueShapeConfig = {
    shape: string;
    component: any;
    inherit?: string;
} & Record<string, any>;
export declare const shapeMaps: Record<string, {
    component: any;
}>;
export declare function register(config: VueShapeConfig): void;

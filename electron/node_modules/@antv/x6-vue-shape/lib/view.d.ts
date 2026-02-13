import { NodeView, Dom, Node } from '@antv/x6';
export declare class VueShapeView extends NodeView<Node> {
    static action: any;
    private vm;
    getComponentContainer(): HTMLDivElement;
    confirmUpdate(flag: number): number;
    protected targetId(): string;
    protected renderVueComponent(): void;
    protected unmountVueComponent(): HTMLDivElement;
    onMouseDown(e: Dom.MouseDownEvent, x: number, y: number): void;
    unmount(): this;
}

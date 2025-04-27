import networkx as nx
from pydantic import BaseModel
from typing import Dict, List, Optional, Set, Union
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os


class Edge(BaseModel):
    source: str
    sourceHandle: str
    target: str
    targetHandle: str
    id: str

    class Config:
        extra = "allow"  # Accept additional fields without error


class WorkflowGraph:
    def __init__(self, edges_data: Optional[List[dict]] = None):
        # Create directed graph
        self.graph = nx.DiGraph()

        # Track component types based on handle IDs
        self.component_handles = {}  # Maps component_id -> {handle_id: direction}

        if edges_data is not None:  # Fixed None check
            self.load_edges(edges_data)

    def load_edges(self, edges_data: List[dict]):
        """Load edges from a list of edge dictionaries."""
        for edge_data in edges_data:
            edge = Edge(**edge_data)
            self.add_edge(edge)

    def add_edge(self, edge: Edge):
        """Add an edge to the graph."""
        # Add nodes if they don't exist
        if not self.graph.has_node(edge.source):
            self.graph.add_node(edge.source)

        if not self.graph.has_node(edge.target):
            self.graph.add_node(edge.target)

        # Add edge with all attributes
        self.graph.add_edge(
            edge.source,
            edge.target,
            id=edge.id,
            sourceHandle=edge.sourceHandle,
            targetHandle=edge.targetHandle,
        )

        # Track handle types
        if edge.source not in self.component_handles:
            self.component_handles[edge.source] = {}
        if edge.target not in self.component_handles:
            self.component_handles[edge.target] = {}

        # Parse handle direction from ID (assumes handle ID ends with -in or -out)
        source_direction = (
            "out" if edge.sourceHandle.endswith("-out") else "out"
        )  # Default to out
        target_direction = (
            "in" if edge.targetHandle.endswith("-in") else "in"
        )  # Default to in

        self.component_handles[edge.source][edge.sourceHandle] = source_direction
        self.component_handles[edge.target][edge.targetHandle] = target_direction

    def get_node_inputs(self, node_id: str) -> List[dict]:
        """Get all incoming connections to a node."""
        inputs = []
        for source, target, data in self.graph.in_edges(node_id, data=True):
            inputs.append(
                {
                    "source_id": source,
                    "source_handle": data["sourceHandle"],
                    "target_handle": data["targetHandle"],
                    "edge_id": data["id"],
                }
            )
        return inputs

    def get_node_outputs(self, node_id: str) -> List[dict]:
        """Get all outgoing connections from a node."""
        outputs = []
        for source, target, data in self.graph.out_edges(node_id, data=True):
            outputs.append(
                {
                    "target_id": target,
                    "source_handle": data["sourceHandle"],
                    "target_handle": data["targetHandle"],
                    "edge_id": data["id"],
                }
            )
        return outputs

    def find_connection_target(
        self, source_component_id: str, source_handle_id: str
    ) -> Optional[tuple[str, str]]:
        """
        Find the target component and handle connected to a specific source component and handle.

        Args:
            source_component_id: ID of the source component
        source_handle_id: ID of the source handle

        Returns:
            A tuple of (target_component_id, target_handle_id) if a connection exists, None otherwise
        """
        # Check if the source component exists in the graph
        if not self.graph.has_node(source_component_id):
            return None

        # Look through all outgoing edges from the source component
        for _, target, data in self.graph.out_edges(source_component_id, data=True):
            # Check if this edge uses the specified source handle
            if data["sourceHandle"] == source_handle_id:
                return (target, data["targetHandle"])

        # No connection found for this source handle
        return None

    def get_roots(self) -> List[str]:
        """Get all nodes with no incoming edges (starting points)."""
        return [node for node in self.graph.nodes if self.graph.in_degree(node) == 0]

    def get_leaves(self) -> List[str]:
        """Get all nodes with no outgoing edges (end points)."""
        return [node for node in self.graph.nodes if self.graph.out_degree(node) == 0]

    def get_component_handles(self, component_id: str) -> Dict[str, str]:
        """Get all handles for a component with their directions."""
        return self.component_handles.get(component_id, {})

    def get_handle_type(self, handle_id: str) -> Optional[str]:
        """Extract the type from a handle ID (assuming format like 'xxxx-type-in/out')."""
        if handle_id.endswith("-in"):
            return handle_id[:-3]  # Remove the "-in" suffix
        elif handle_id.endswith("-out"):
            return handle_id[:-4]  # Remove the "-out" suffix
        return handle_id

    def get_execution_order(self) -> List[str]:
        """Get a possible execution order for the workflow (topological sort)."""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # If there's a cycle, this won't work
            return []

    def has_cycles(self) -> bool:
        """Check if the workflow contains cycles."""
        return not nx.is_directed_acyclic_graph(self.graph)

    def get_path_between(self, source_id: str, target_id: str) -> List[str]:
        """Find a path between two nodes if it exists."""
        try:
            return nx.shortest_path(self.graph, source_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def to_json(self) -> str:
        """Convert the graph back to JSON edge representation."""
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append(
                {
                    "source": u,
                    "target": v,
                    "sourceHandle": data["sourceHandle"],
                    "targetHandle": data["targetHandle"],
                    "id": data["id"],
                }
            )
        return json.dumps(edges)

    def visualize(
        self,
        figsize=(12, 8),
        title="Workflow Graph Visualization",
        show_handles=False,
        save_path=None,
        save_format="png",
        dpi=300,
    ):
        """
        Create a visualization of the workflow graph

        Args:
            figsize: Size of the figure (width, height) in inches
            title: Title of the visualization
            show_handles: Whether to show handle IDs on the edges
            save_path: Path to save the visualization file. If None, won't save.
            save_format: Format to save the image (png, jpg, svg, pdf)
            dpi: Resolution for saved image

        Returns:
            The matplotlib figure object
        """
        plt.figure(figsize=figsize)

        # Extract node types from their first handle if possible
        node_types = {}
        for node in self.graph.nodes:
            node_type = "unknown"
            if node in self.component_handles and self.component_handles[node]:
                # Try to extract a short type from the first handle ID
                first_handle = list(self.component_handles[node].keys())[0]
                parts = first_handle.split("-")
                if len(parts) > 1:
                    # Use the part before the last segment (which is usually 'in' or 'out')
                    node_type = parts[-2] if len(parts) > 2 else parts[0][:3]
            node_types[node] = node_type

        # Generate a layout - hierarchical layout works well for workflows
        try:
            pos = nx.nx_pydot.pydot_layout(self.graph, prog="dot")
        except:
            # Fallback to another layout if pydot is not available
            try:
                pos = nx.drawing.nx_agraph.graphviz_layout(self.graph, prog="dot")
            except:
                # If both fail, use spring layout
                pos = nx.spring_layout(self.graph, seed=42)

        # Group nodes by type for coloring
        unique_types = set(node_types.values())

        # Fixed tab20 colormap issue - use a different colormap or create colors manually
        # colormap = plt.cm.tab20  # This causes an error

        # Create a color map manually
        colors = {}
        colorlist = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
            "#aec7e8",
            "#ffbb78",
            "#98df8a",
            "#ff9896",
            "#c5b0d5",
            "#c49c94",
            "#f7b6d2",
            "#c7c7c7",
            "#dbdb8d",
            "#9edae5",
        ]

        for i, t in enumerate(unique_types):
            colors[t] = colorlist[i % len(colorlist)]

        # Color nodes by their type - fixed by making sure we have a list of colors
        node_colors = [colors[node_types[n]] for n in self.graph.nodes]

        # Draw nodes - fixed node_color parameter
        nx.draw_networkx_nodes(
            self.graph,
            pos,
            node_color=node_colors,  # This is now correctly a list of color strings
            node_size=2000,
            alpha=0.8,
        )

        # Draw edges with arrowheads to show direction
        nx.draw_networkx_edges(
            self.graph, pos, arrowstyle="->", arrowsize=15, edge_color="gray", width=1.5
        )

        # Draw component IDs as labels
        nx.draw_networkx_labels(self.graph, pos, font_size=10, font_weight="bold")

        # Draw handle information on edges if requested
        if show_handles:
            edge_labels = {}
            for u, v, data in self.graph.edges(data=True):
                # Show a shortened version of the handles
                source_handle = (
                    data["sourceHandle"].split("-")[-2]
                    if len(data["sourceHandle"].split("-")) > 2
                    else "out"
                )
                target_handle = (
                    data["targetHandle"].split("-")[-2]
                    if len(data["targetHandle"].split("-")) > 2
                    else "in"
                )
                edge_labels[(u, v)] = f"{source_handle} → {target_handle}"

            nx.draw_networkx_edge_labels(
                self.graph, pos, edge_labels=edge_labels, font_size=8
            )

        # Create legend for node types
        legend_patches = [
            mpatches.Patch(color=colors[t], label=t) for t in unique_types
        ]
        plt.legend(handles=legend_patches, loc="upper right")

        # Highlight start and end nodes
        roots = self.get_roots()
        leaves = self.get_leaves()

        # Draw a green border around root nodes
        if roots:
            nx.draw_networkx_nodes(
                self.graph,
                pos,
                nodelist=roots,
                node_color="none",
                node_size=2200,
                node_shape="o",
                edgecolors="green",
                linewidths=3,
            )

        # Draw a red border around leaf nodes
        if leaves:
            nx.draw_networkx_nodes(
                self.graph,
                pos,
                nodelist=leaves,
                node_color="none",
                node_size=2200,
                node_shape="o",
                edgecolors="red",
                linewidths=3,
            )

        # Add execution order markers
        if not self.has_cycles():
            execution_order = self.get_execution_order()
            for i, node in enumerate(execution_order):
                plt.annotate(
                    f"#{i + 1}",
                    xy=pos[node],
                    xytext=(-15, -30),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7),
                    fontsize=8,
                )

        plt.title(title)
        plt.axis("off")  # Hide axis
        plt.tight_layout()

        # Save the figure if a path is provided
        if save_path:
            # If save_path doesn't include the extension, add it
            if not save_path.lower().endswith(f".{save_format}"):
                save_path = f"{save_path}.{save_format}"

            # Ensure the directory exists
            directory = os.path.dirname(save_path)
            if directory:
                os.makedirs(directory, exist_ok=True)

            # Save the figure
            plt.savefig(save_path, format=save_format, dpi=dpi, bbox_inches="tight")
            print(f"Graph visualization saved to {save_path}")

        plt.show()

        return plt.gcf()  # Return the figure for further modification if needed


json_str = [
    {
        "source": "0f4f11f7-c2e2-4589-b986-e47eac2267c5",
        "sourceHandle": "e1060e64-ee2d-4e59-9ba9-8a4f0f030946-out",
        "target": "ef74a71f-c33c-4fe3-bd5b-bf312710caad",
        "targetHandle": "jkj-in",
        "id": "xy-edge__0f4f11f7-c2e2-4589-b986-e47eac2267c5e1060e64-ee2d-4e59-9ba9-8a4f0f030946-out-ef74a71f-c33c-4fe3-bd5b-bf312710caadjkj-in",
    },
    {
        "source": "ef74a71f-c33c-4fe3-bd5b-bf312710caad",
        "sourceHandle": "jkj-out",
        "target": "d47e816f-e377-4a88-9ec8-1e9eeba6d283",
        "targetHandle": "pppp-in",
        "id": "xy-edge__ef74a71f-c33c-4fe3-bd5b-bf312710caadjkj-out-d47e816f-e377-4a88-9ec8-1e9eeba6d283pppp-in",
    },
    {
        "source": "fcb01b6e-65b1-4310-afb1-ea85ffdd9379",
        "sourceHandle": "d20a2694-20ea-4e48-96f0-915863018bbd-out",
        "target": "ef74a71f-c33c-4fe3-bd5b-bf312710caad",
        "targetHandle": "jkj-in",
        "id": "xy-edge__fcb01b6e-65b1-4310-afb1-ea85ffdd9379d20a2694-20ea-4e48-96f0-915863018bbd-out-ef74a71f-c33c-4fe3-bd5b-bf312710caadjkj-in",
    },
    {
        "source": "d47e816f-e377-4a88-9ec8-1e9eeba6d283",
        "sourceHandle": "pppp-out",
        "target": "37bdcb20-1d0e-4a45-ab7c-33d2d738adab",
        "targetHandle": "eqw-in",
        "id": "xy-edge__d47e816f-e377-4a88-9ec8-1e9eeba6d283pppp-out-37bdcb20-1d0e-4a45-ab7c-33d2d738adabeqw-in",
    },
    {
        "source": "37bdcb20-1d0e-4a45-ab7c-33d2d738adab",
        "sourceHandle": "eqw-out",
        "target": "ef74a71f-c33c-4fe3-bd5b-bf312710caad",
        "targetHandle": "jkj-in",
        "id": "xy-edge__37bdcb20-1d0e-4a45-ab7c-33d2d738adabeqw-out-ef74a71f-c33c-4fe3-bd5b-bf312710caadjkj-in",
    },
]


# Example usage
def load_workflow_from_json(json_str):
    edges_data = json.loads(json_str)
    return WorkflowGraph(edges_data)


# You would use it like this:
workflow = WorkflowGraph(json_str)
# execution_order = workflow.get_execution_order()
# print("Execution Order:", execution_order)
# has_cycles = workflow.has_cycles()
# print("Has Cycles:", has_cycles)
# get_roots = workflow.get_roots()
# print("Roots:", get_roots)
# comp = workflow.get_component_handles("ef74a71f-c33c-4fe3-bd5b-bf312710caad")
# print("Component Handles:", comp)
# out = workflow.find_connection_target("ef74a71f-c33c-4fe3-bd5b-bf312710caad", "jkj-out")
# print("Node Outputs:", out)

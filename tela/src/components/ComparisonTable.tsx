import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Species } from "@/data/mockData";

interface ComparisonTableProps {
  species: Species[];
}

const ComparisonTable = ({ species }: ComparisonTableProps) => {
  if (species.length === 0) {
    return null;
  }

  const attributes = [
    { key: "size", label: "Porte" },
    { key: "height", label: "Altura" },
    { key: "rootType", label: "Tipo de raiz" },
    { key: "shading", label: "Sombreamento" },
    { key: "maintenance", label: "Manutenção" },
  ];

  const getAttributeValue = (species: Species, key: string): string => {
    switch (key) {
      case "size":
        return species.size;
      case "height":
        return species.height;
      case "rootType":
        return species.rootType;
      case "shading":
        return species.shading;
      case "maintenance":
        return species.maintenance;
      default:
        return "";
    }
  };

  return (
    <div className="card-elevated p-5">
      <h2 className="text-lg font-semibold text-foreground mb-4">
        Comparar Espécies Selecionadas ({species.length})
      </h2>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-foreground font-semibold">Atributo</TableHead>
              {species.map((s) => (
                <TableHead key={s.id} className="text-foreground font-semibold">
                  {s.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {attributes.map((attr) => (
              <TableRow
                key={attr.key}
                className="border-border hover:bg-secondary/30"
              >
                <TableCell className="font-medium text-foreground">
                  {attr.label}
                </TableCell>
                {species.map((s) => (
                  <TableCell key={s.id} className="text-muted-foreground">
                    {getAttributeValue(s, attr.key)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="mt-5 flex justify-center">
        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground px-8">
          Adicionar ao plano de plantio
        </Button>
      </div>
    </div>
  );
};

export default ComparisonTable;

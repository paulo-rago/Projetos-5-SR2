import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const ComparisonTable = () => {
  const data = [
    { attribute: "Porte", ipe: "Médio", manga: "Grande", craibeira: "Pequeno" },
    { attribute: "Altura", ipe: "8–15m", manga: "15–30m", craibeira: "4–8m" },
    { attribute: "Tipo de raiz", ipe: "Profunda", manga: "Agressiva", craibeira: "Superficial" },
    { attribute: "Sombreamento", ipe: "Alto", manga: "Muito alto", craibeira: "Médio" },
    { attribute: "Manutenção", ipe: "Baixa", manga: "Média", craibeira: "Baixa" },
  ];

  return (
    <div className="card-elevated p-5">
      <h2 className="text-lg font-semibold text-foreground mb-4">
        Comparar Espécies Selecionadas
      </h2>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-border hover:bg-transparent">
              <TableHead className="text-foreground font-semibold">Atributo</TableHead>
              <TableHead className="text-foreground font-semibold">Ipê Amarelo</TableHead>
              <TableHead className="text-foreground font-semibold">Mangueira</TableHead>
              <TableHead className="text-foreground font-semibold">Craibeira</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.attribute} className="border-border hover:bg-secondary/30">
                <TableCell className="font-medium text-foreground">{row.attribute}</TableCell>
                <TableCell className="text-muted-foreground">{row.ipe}</TableCell>
                <TableCell className="text-muted-foreground">{row.manga}</TableCell>
                <TableCell className="text-muted-foreground">{row.craibeira}</TableCell>
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
